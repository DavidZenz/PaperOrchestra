"""Bundle freeze/hash tests using temporary labelled skill fixtures."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("paper_orchestra_bundle_test", ROOT / "paper-orchestra/scripts/bundle.py")
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "skill"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("labelled skill fixture")
        (self.source / "script.py").write_text("print('fixture')\n")

    def test_manifest_is_stable_and_includes_every_source_file(self):
        first = BUNDLE.manifest(self.source)
        second = BUNDLE.manifest(self.source)
        self.assertEqual(first, second)
        self.assertEqual(set(first["files"]), {"SKILL.md", "script.py"})
        self.assertEqual(len(first["sha256"]), 64)

    def test_interpreter_caches_do_not_change_frozen_source_identity(self):
        first = BUNDLE.manifest(self.source)
        (self.source / "__pycache__").mkdir()
        (self.source / "__pycache__/script.cpython-test.pyc").write_bytes(b"cache")
        (self.source / ".DS_Store").write_bytes(b"OS metadata")
        self.assertEqual(first, BUNDLE.manifest(self.source))

    def test_snapshot_remains_identical_after_source_is_edited(self):
        destination = self.root / "snapshot"
        frozen = BUNDLE.snapshot(self.source, destination)
        self.assertEqual(frozen, BUNDLE.manifest(destination))
        (self.source / "script.py").write_text("print('later source version')\n")
        self.assertEqual(frozen, BUNDLE.manifest(destination))
        self.assertNotEqual(frozen, BUNDLE.manifest(self.source))
        self.assertEqual((destination / "script.py").read_text(), "print('fixture')\n")

    def test_snapshot_tampering_changes_recorded_hash_identity(self):
        destination = self.root / "snapshot"
        frozen = BUNDLE.snapshot(self.source, destination)
        (destination / "script.py").write_text("tampered source")
        self.assertNotEqual(frozen, BUNDLE.manifest(destination))
        self.assertNotEqual(frozen["sha256"], BUNDLE.manifest(destination)["sha256"])

    def test_change_during_snapshot_is_detected(self):
        original_copy = shutil.copyfile
        mutated = False
        def copy_then_mutate(src, dst):
            nonlocal mutated
            result = original_copy(src, dst)
            if not mutated:
                (self.source / "script.py").write_text("changed while copying")
                mutated = True
            return result
        with patch.object(BUNDLE.shutil, "copyfile", side_effect=copy_then_mutate):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                BUNDLE.snapshot(self.source, self.root / "snapshot")

    def test_source_changed_after_its_copy_is_also_detected(self):
        original_copy = shutil.copyfile
        mutated = False
        def copy_then_change_already_copied_source(src, dst):
            nonlocal mutated
            result = original_copy(src, dst)
            if not mutated:
                Path(src).write_text("changed after its original bytes were copied")
                mutated = True
            return result
        with patch.object(BUNDLE.shutil, "copyfile", side_effect=copy_then_change_already_copied_source):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                BUNDLE.snapshot(self.source, self.root / "snapshot")


if __name__ == "__main__":
    unittest.main(verbosity=2)
