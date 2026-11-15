"""Provenance verification against bundled bytes and a real local Git source."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "paper-orchestra"
SOURCE = ROOT / "upstream"
SCRIPT = SKILL / "scripts/verify_upstream.py"
SPEC = importlib.util.spec_from_file_location("paper_orchestra_verify_upstream", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class SourceLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="paper-orchestra-source-lock-")
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)

    def bundle_copy(self):
        bundle = self.scratch / "bundle"
        bundle.mkdir()
        shutil.copy2(SKILL / "upstream-lock.json", bundle / "upstream-lock.json")
        shutil.copytree(SKILL / "vendor", bundle / "vendor", ignore=shutil.ignore_patterns("__pycache__"))
        return bundle

    def git(self, path, *args):
        result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=True)
        return result.stdout.decode().strip()

    def has_source(self):
        return (SOURCE / ".git").exists() and shutil.which("git") is not None

    def local_source_copy(self):
        if not self.has_source():
            self.skipTest("Optional upstream checkout unavailable; no network fetch is attempted")
        source = self.scratch / "upstream"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", str(SOURCE), str(source)], capture_output=True, check=True)
        lock = json.loads((SKILL / "upstream-lock.json").read_text())
        paths = [item["path"] for item in lock["files"] + lock["adapter_sources"]]
        self.git(source, "checkout", "HEAD", "--", *paths)
        return source

    def test_actual_bundle_verifies_without_source_or_runtime_dependencies(self):
        report = verifier.verify(SKILL)
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["counts"]["vendor_hashes_verified"], 20)
        self.assertEqual(report["counts"]["gemini_functions_verified"], 7)
        self.assertEqual(report["source"]["status"], "not-requested")
        self.assertEqual(report, verifier.verify(SKILL), "Machine report must be deterministic")

    def test_actual_pinned_source_blobs_and_checkout_verify(self):
        if not self.has_source():
            self.skipTest("Optional upstream checkout unavailable; no network fetch is attempted")
        report = verifier.verify(SKILL, SOURCE)
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["source"]["head"], verifier.PINNED_COMMIT)
        self.assertEqual(report["source"]["status"], "verified")
        self.assertEqual(report["counts"]["source_files_verified"], 22)
        self.assertTrue(any(c["kind"] == "direct_gemini_function_comparison" and c["ok"] for c in report["checks"]))

    def test_corrupt_vendored_file_is_detected_without_touching_real_bundle(self):
        bundle = self.bundle_copy()
        target = bundle / "vendor/methods/agents/outline_agent.py"
        target.write_bytes(target.read_bytes() + b"\n# corruption\n")
        report = verifier.verify(bundle)
        self.assertFalse(report["ok"])
        self.assertTrue(any(c["kind"] == "vendor_sha256" and c["path"] == "methods/agents/outline_agent.py" for c in report["failures"]))
        self.assertTrue(verifier.verify(SKILL)["ok"])

    def test_retry_loop_ast_mutation_is_detected_even_though_adapter_not_byte_locked(self):
        bundle = self.bundle_copy()
        target = bundle / "vendor/utils/gemini_utils.py"
        text = target.read_text()
        self.assertIn("for attempt in range(max_retries):", text)
        target.write_text(text.replace("for attempt in range(max_retries):", "for attempt in range(1):", 1))
        report = verifier.verify(bundle)
        self.assertFalse(report["ok"])
        self.assertTrue(any(c["kind"] == "gemini_function_ast" and c["path"] == "call_gemini_with_contents" for c in report["failures"]))
        self.assertFalse(any(c["kind"] == "vendor_sha256" for c in report["failures"]))

    def test_top_level_transport_annotation_does_not_change_original_function_asts(self):
        bundle = self.bundle_copy()
        target = bundle / "vendor/utils/gemini_utils.py"
        target.write_text(target.read_text() + "\n# transport-only annotation\n")
        report = verifier.verify(bundle)
        self.assertTrue(report["ok"], report["failures"])

    def test_wrong_git_head_is_rejected(self):
        if shutil.which("git") is None:
            self.skipTest("Git unavailable")
        source = self.scratch / "wrong-source"
        source.mkdir()
        self.git(source, "init")
        self.git(source, "-c", "user.name=Source Lock Test", "-c", "user.email=source-lock@example.invalid", "commit", "--allow-empty", "-m", "unrelated source")
        report = verifier.verify(SKILL, source)
        self.assertFalse(report["ok"])
        self.assertEqual(report["source"]["status"], "failed")
        self.assertTrue(any(c["kind"] == "source_commit" for c in report["failures"]))

    def test_dirty_source_file_is_detected_with_pinned_head_unchanged(self):
        source = self.local_source_copy()
        target = source / "utils/prompt_utils.py"
        target.write_bytes(target.read_bytes() + b"\n# uncommitted scientific prompt edit\n")
        report = verifier.verify(SKILL, source)
        self.assertFalse(report["ok"])
        self.assertEqual(report["source"]["head"], verifier.PINNED_COMMIT)
        self.assertTrue(any(c["kind"] == "source_checkout_sha256" and c["path"] == "utils/prompt_utils.py" for c in report["failures"]))
        self.assertFalse(any(c["kind"] == "source_committed_sha256" for c in report["failures"]))

    def test_source_hash_is_checked_against_git_blob_not_trusted_manifest(self):
        if not self.has_source():
            self.skipTest("Optional upstream checkout unavailable; no network fetch is attempted")
        bundle = self.bundle_copy()
        target = bundle / "upstream-lock.json"
        lock = json.loads(target.read_text())
        lock["files"][0]["upstream_sha256"] = "0" * 64
        target.write_text(json.dumps(lock))
        report = verifier.verify(bundle, SOURCE)
        self.assertFalse(report["ok"])
        self.assertTrue(any(c["kind"] == "source_committed_sha256" for c in report["failures"]))

    def test_cli_reports_json_and_nonzero_on_corruption(self):
        bundle = self.bundle_copy()
        (bundle / "vendor/LICENSE").unlink()
        process = subprocess.run([sys.executable, str(SCRIPT), "--skill-dir", str(bundle)], text=True, capture_output=True)
        self.assertEqual(process.returncode, 1)
        report = json.loads(process.stdout)
        self.assertFalse(report["ok"])
        self.assertTrue(any(c["path"] == "LICENSE" for c in report["failures"]))


if __name__ == "__main__":
    unittest.main()
