"""Driver must not trust upstream success when references are empty."""
import importlib.util
import json
import subprocess
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper-orchestra/scripts"))
spec = importlib.util.spec_from_file_location("bibliography_driver", ROOT / "paper-orchestra/scripts/run.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class DriverGateTests(unittest.TestCase):
    def test_http_exception_url_cannot_leak_api_key_into_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = """
import sys
import requests
from orchestra_runtime import Runtime, configure, instrument
configure(Runtime(sys.argv[1]))
def fail(*args, **kwargs):
    raise RuntimeError('https://example.test/?api_key=SECRET_TEST_VALUE')
requests.get = fail
instrument(sys.argv[1])
try:
    requests.get('https://example.test', params={'api_key':'SECRET_TEST_VALUE'})
except RuntimeError:
    pass
"""
            import os
            env = dict(os.environ, PYTHONPATH=str(ROOT / "paper-orchestra/vendor"))
            result = subprocess.run([sys.executable, "-c", script, tmp], env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            trace = (Path(tmp) / "trace.jsonl").read_text()
            self.assertNotIn("SECRET_TEST_VALUE", trace)
            events = [json.loads(line) for line in trace.splitlines()]
            self.assertEqual(events[-1]["error_type"], "RuntimeError")

    def test_successful_controller_with_empty_bibliography_cannot_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            materials = base / "materials"
            template = base / "template"
            materials.mkdir()
            template.mkdir()
            for name in ["idea_sparse.md", "experimental_log.md"]:
                (materials / name).write_text("Labelled driver fixture")
            for name in ["template.tex", "guidelines.md"]:
                (template / name).write_text("Labelled driver fixture")
            output = base / "output"
            def controller(**kwargs):
                (output / "final_paper.pdf").write_bytes(b"Labelled non-PDF controller-success fixture")
                library = output / "literature_agent_output"
                library.mkdir()
                (library / "references.bib").write_text("")
                (library / "citation_map.json").write_text("{}")
                return True
            # No external models, transport, tools or real paper creation.
            with patch.object(driver, "preflight", return_value=[]), \
                 patch.object(driver, "instrument"), \
                 patch.object(driver.Runtime, "generate", return_value=SimpleNamespace(text="PAPER_ORCHESTRA_RUNTIME_OK")), \
                 patch.object(driver.subprocess, "run", return_value=SimpleNamespace(stdout="labelled version")), \
                 patch("methods.paper_writer.write_single_paper", side_effect=controller):
                result = driver.main(["--materials", str(materials), "--template", str(template), "--output", str(output)])
            manifest = json.loads((output / "run.json").read_text())
            self.assertEqual(result, 1)
            self.assertEqual(manifest["status"], "failed")
            self.assertTrue(manifest["bibliography_required"])
            self.assertIn("Empty bibliography", manifest["error"])
