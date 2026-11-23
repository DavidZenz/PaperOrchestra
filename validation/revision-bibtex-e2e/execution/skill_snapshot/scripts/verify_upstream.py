#!/usr/bin/env python3
"""Verify bundled source provenance without importing runtime dependencies or networking."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

PINNED_COMMIT = "ca1b3fa01c2970fc7cda32d16245db38d57b3f56"
REPOSITORY = "https://github.com/google-research/paper-orchestra"
GEMINI_SOURCE_SHA256 = "024fc69a59bda7522f04262a7c21cc918733033c71ccf5a9edd7c3c3ee8ddbe3"
# Derived from every original top-level function at PINNED_COMMIT. Canonical AST
# includes signature, decorators, docstring and body; excludes location metadata
# and empty type_params (added in Python 3.12). No Gemini client import is needed.
GEMINI_FUNCTION_SHA256 = {
    "parse_gemini_json_results": "1fde746c8c4e9483f8ad7536053b8adc637ff54e61435958887d2ce0c170303a",
    "parse_gemini_latex_results": "77489e95b1f89985eb4432677cc87fd66f0415af28f92d1e3b68b4b93534d06e",
    "parse_gemini_json_latex_response": "b4918ad77b324f295db2bdc10ab4003f6758ff50b845949e2ffe97b511b6a594",
    "call_gemini_with_contents": "c48917bd4828365c10c9938231f5faeb86e29587c5309ce6b730f21f81c57367",
    "call_gemini_with_text_prompt": "4831c3f89a6ddca40018477445b52e626a9297e4962c01f8e5723e2bf4534cb5",
    "call_gemini_with_images": "5aca6f27079802fe9d26c45f5174c4d797f341c0d5188e870a8e9de12dfb73e9",
    "generate_image_with_gemini": "b73c87e34b3397eb32dd34e9192f92257a2dcb84b4be149373ddbbe08fdb3703",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_ast(node):
    if isinstance(node, ast.AST):
        return {"_type": type(node).__name__, **{
            name: canonical_ast(value) for name, value in ast.iter_fields(node)
            if not (name == "type_params" and not value)
        }}
    if isinstance(node, list):
        return [canonical_ast(item) for item in node]
    return node


def function_hashes(data: bytes) -> dict[str, str]:
    functions = {}
    for node in ast.parse(data.decode("utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in functions:
                raise ValueError(f"Duplicate function definition: {node.name}")
            serialized = json.dumps(canonical_ast(node), sort_keys=True, separators=(",", ":"))
            functions[node.name] = sha256(serialized.encode("utf-8"))
    return functions


def _relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or str(path) != value:
        raise ValueError(f"Unsafe or noncanonical locked path: {value!r}")
    return value


def _git(source: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, timeout=20)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def verify(skill_dir: Path | str | None = None, source_dir: Path | str | None = None) -> dict:
    """Return a deterministic JSON-serializable report; never alter checked files."""
    skill = Path(skill_dir or Path(__file__).resolve().parents[1]).resolve()
    source = Path(source_dir).resolve() if source_dir is not None else None
    checks = []
    report = {
        "schema_version": 1,
        "ok": False,
        "repository": REPOSITORY,
        "expected_commit": PINNED_COMMIT,
        "skill_dir": str(skill),
        "source": {"status": "not-requested" if source is None else "pending", "path": str(source) if source else None},
        "counts": {"locked_files": 0, "vendor_hashes_verified": 0, "source_files_verified": 0, "gemini_functions_verified": 0},
        "checks": checks,
        "adapter_policy": {
            "utils/gemini_utils.py": "All seven original function ASTs must match; top-level Codex transport initialization/wrapper allowed.",
            "utils/llm_backend_utils.py": "Fully adapted transport module: existence checked, no upstream byte-equivalence claimed; see references/adaptations.md.",
        },
    }

    def check(kind, path, expected=None, actual=None, *, error=None):
        ok = error is None and expected == actual
        entry = {"kind": kind, "path": path, "ok": ok}
        if expected is not None:
            entry["expected"] = expected
        if actual is not None:
            entry["actual"] = actual
        if error is not None:
            entry["error"] = str(error)
        checks.append(entry)
        return ok

    try:
        lock = json.loads((skill / "upstream-lock.json").read_text())
        check("lock_schema", "upstream-lock.json", 1, lock["schema_version"])
        check("lock_commit", "upstream-lock.json", PINNED_COMMIT, lock["commit"])
        check("lock_repository", "upstream-lock.json", REPOSITORY, lock["repository"])
        records = lock["files"] + lock["adapter_sources"]
        paths = [_relative_path(item["path"]) for item in records]
        if len(set(paths)) != len(paths):
            raise ValueError("Duplicate locked file path")
        report["counts"]["locked_files"] = len(lock["files"])
        gemini_source = next(item for item in lock["adapter_sources"] if item["path"] == "utils/gemini_utils.py")
        check("gemini_original_hash_anchor", gemini_source["path"], GEMINI_SOURCE_SHA256, gemini_source["upstream_sha256"])
    except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        check("lock_read", "upstream-lock.json", error=exc)
        report["failures"] = [item for item in checks if not item["ok"]]
        return report

    for item in lock["files"]:
        path = item["path"]
        try:
            actual = sha256((skill / "vendor" / path).read_bytes())
            if check("vendor_sha256", path, item["vendored_sha256"], actual):
                report["counts"]["vendor_hashes_verified"] += 1
        except (OSError, KeyError) as exc:
            check("vendor_sha256", path, error=exc)

    adapter_functions = None
    try:
        adapter_functions = function_hashes((skill / "vendor/utils/gemini_utils.py").read_bytes())
        check("gemini_function_names", "utils/gemini_utils.py", sorted(GEMINI_FUNCTION_SHA256), sorted(adapter_functions))
        for name, expected in GEMINI_FUNCTION_SHA256.items():
            if check("gemini_function_ast", name, expected, adapter_functions.get(name)):
                report["counts"]["gemini_functions_verified"] += 1
    except (OSError, ValueError, SyntaxError) as exc:
        check("gemini_function_ast", "utils/gemini_utils.py", error=exc)
    check("adapted_module_exists", "utils/llm_backend_utils.py", True, (skill / "vendor/utils/llm_backend_utils.py").is_file())

    if source is not None:
        try:
            git_root = Path(_git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve()
            check("source_root", str(source), str(source), str(git_root))
            head = _git(source, "rev-parse", "HEAD").decode().strip()
            report["source"]["head"] = head
            valid_head = check("source_commit", str(source), PINNED_COMMIT, head)
            if valid_head:
                for item in records:
                    path = item["path"]
                    try:
                        committed = _git(source, "show", f"HEAD:{path}")
                        committed_ok = check("source_committed_sha256", path, item["upstream_sha256"], sha256(committed))
                        working_ok = check("source_checkout_sha256", path, item["upstream_sha256"], sha256((source / path).read_bytes()))
                        if committed_ok and working_ok:
                            report["counts"]["source_files_verified"] += 1
                        if path == "utils/gemini_utils.py":
                            original_functions = function_hashes(committed)
                            check("source_gemini_ast_anchor", path, GEMINI_FUNCTION_SHA256, original_functions)
                            check("direct_gemini_function_comparison", path, original_functions, adapter_functions)
                    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
                        check("source_file", path, error=exc)
            source_checks = [item for item in checks if item["kind"].startswith("source_") or item["kind"] == "direct_gemini_function_comparison"]
            report["source"]["status"] = "verified" if all(item["ok"] for item in source_checks) else "failed"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            check("source_git", str(source), error=exc)
            report["source"]["status"] = "failed"

    report["failures"] = [item for item in checks if not item["ok"]]
    report["ok"] = not report["failures"]
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, help="Skill bundle to verify (defaults to this script's parent)")
    parser.add_argument("--source", type=Path, help="Optional local upstream Git checkout; must have pinned HEAD and matching source files")
    args = parser.parse_args(argv)
    report = verify(args.skill_dir, args.source)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
