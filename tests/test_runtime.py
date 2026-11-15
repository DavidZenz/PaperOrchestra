"""Transport tests. Fake responses are explicitly fixtures, never scientific evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

VENDOR = Path(__file__).resolve().parents[1] / "paper-orchestra" / "vendor"
sys.path.insert(0, str(VENDOR))
from google.genai import types
from orchestra_runtime import Runtime, CapabilityError, configure, executed_search
from utils.gemini_utils import call_gemini_with_contents, generate_image_with_gemini


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def events(self, runtime):
        return [json.loads(s) for s in (runtime.root / "trace.jsonl").read_text().splitlines()]

    def test_upstream_retry_loop_retries_parse_failure_five_times_with_original_backoff(self):
        calls = []
        def executor(command, prompt, directory):
            calls.append(directory)
            return "invalid json"
        runtime = Runtime(self.root, executor=executor)
        configure(runtime)
        with patch("utils.gemini_utils.time.sleep") as sleep:
            with self.assertRaises(AssertionError):
                call_gemini_with_contents([types.Part(text="fixture")], "upstream-model")
        self.assertEqual(len(calls), 5)
        self.assertEqual(len(set(calls)), 5)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [5, 10, 20])
        self.assertEqual(sum(e["event"] == "agent_start" for e in self.events(runtime)), 5)

    def test_upstream_retry_recovers_on_third_attempt(self):
        outputs = iter(["bad", "still bad", '{"ok": true}'])
        runtime = Runtime(self.root, executor=lambda *args: next(outputs))
        configure(runtime)
        with patch("utils.gemini_utils.time.sleep"):
            response = call_gemini_with_contents([types.Part(text="fixture")], "original")
        self.assertEqual(response["parsed_response"], {"ok": True})
        self.assertEqual(sum(e["event"] == "agent_start" for e in self.events(runtime)), 3)

    def test_original_nonretryable_400_stops_immediately(self):
        calls = []
        def executor(*args):
            calls.append(1)
            raise RuntimeError("400 bad request")
        configure(Runtime(self.root, executor=executor))
        with self.assertRaisesRegex(RuntimeError, "400 bad request"):
            call_gemini_with_contents([types.Part(text="fixture")], "original")
        self.assertEqual(calls, [1])

    def test_search_requires_actual_search_event_even_when_json_is_valid(self):
        runtime = Runtime(self.root, executor=lambda *args: '{"candidates": []}')
        with self.assertRaisesRegex(RuntimeError, "web_search"):
            runtime.generate([types.Part(text="search")], {"tools": [{"google_search": {}}]}, "original")
        self.assertEqual(len(runtime.pending_search), 1)

    def test_agent_prose_mentioning_search_cannot_forge_tool_evidence(self):
        def executor(command, prompt, directory):
            (directory / "events.jsonl").write_text(json.dumps({"type":"item.completed", "item":{"type":"agent_message", "text":"I used web_search"}}) + "\n")
            return '{}'
        runtime = Runtime(self.root, executor=executor)
        with self.assertRaisesRegex(RuntimeError, "web_search"):
            runtime.generate(["search"], {"tools":[{"google_search":{}}]}, "original")

    def test_recovered_search_retry_clears_unresolved_capability(self):
        outputs = iter([False, True])
        def executor(command, prompt, directory):
            item = {"type":"web_search"} if next(outputs) else {"type":"agent_message", "text":"web_search"}
            (directory / "events.jsonl").write_text(json.dumps({"type":"item.completed", "item":item}) + "\n")
            return '{}'
        runtime = Runtime(self.root, executor=executor)
        configure(runtime)
        with patch("utils.gemini_utils.time.sleep"):
            call_gemini_with_contents(["search"], "original", generation_configs={"tools":[types.Tool(google_search=types.GoogleSearch())]})
        self.assertFalse(runtime.pending_search)
        self.assertFalse(runtime.fatal)

    def test_search_evidence_and_tool_configuration_are_recorded(self):
        seen = []
        def executor(command, prompt, directory):
            seen.append((command, prompt))
            # JSONL uses physical LF; U+0085 is valid inside a JSON string.
            (directory / "events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {"type": "web_search", "result":{"text":"left\u0085right"}}}, ensure_ascii=False) + "\n")
            return '{"candidates": []}'
        runtime = Runtime(self.root, executor=executor)
        runtime.generate([types.Part(text="search")], {"tools": [{"google_search": {}}]}, "original")
        self.assertIn('web_search="live"', seen[0][0])
        self.assertIn("Use live web search", seen[0][1])
        self.assertTrue(self.events(runtime)[-1]["searched"])

    def test_connected_search_tool_requires_successful_completed_tool_event(self):
        event = {"type":"item.completed", "item":{"type":"mcp_tool_call", "server":"codex_apps",
                 "tool":"search_service.web_run", "status":"completed", "error":None}}
        self.assertTrue(executed_search([event]))
        event["item"]["error"] = {"message":"tool unavailable"}
        self.assertFalse(executed_search([event]))
        event["item"]["error"] = None
        event["item"]["status"] = "in_progress"
        self.assertFalse(executed_search([event]))

    def test_each_invocation_uses_fresh_process_and_fresh_session(self):
        # Genuine subprocesses, but a labelled fixture executable instead of a model.
        fixture = self.root / "fake_agent.py"
        fixture.write_text('import json,sys,uuid,os\nfrom pathlib import Path\n'
                           'sys.stdin.read()\nPath(sys.argv[1]).write_text(json.dumps({"pid": os.getpid()}))\n'
                           'print(json.dumps({"type":"thread.started","thread_id":str(uuid.uuid4())}))\n'
                           'print(json.dumps({"type":"turn.completed"}))\n')
        runtime = Runtime(self.root / "execution")
        def executor(command, prompt, directory):
            return runtime._execute([sys.executable, str(fixture), str(directory / "response.txt")], prompt, directory)
        runtime.executor = executor
        results = [runtime.generate(["fixture"], {}, "original") for _ in range(2)]
        self.assertNotEqual(json.loads(results[0].text)["pid"], json.loads(results[1].text)["pid"])
        ends = [e for e in self.events(runtime) if e["event"] == "agent_end"]
        self.assertNotEqual(ends[0]["sessions"], ends[1]["sessions"])
        self.assertEqual(len([e for e in self.events(runtime) if e["event"] == "process_started"]), 2)

    def test_process_failure_and_timeout_never_fabricate_success(self):
        runtime = Runtime(self.root, timeout=0.05)
        directory = self.root / "call"
        directory.mkdir()
        with self.assertRaises(RuntimeError):
            runtime._execute([sys.executable, "-c", "raise SystemExit(7)"], "", directory)
        with self.assertRaises(TimeoutError):
            runtime._execute([sys.executable, "-c", "import time; time.sleep(10)"], "", directory)

    def test_shell_metacharacters_remain_literal_model_argument(self):
        seen = []
        model = 'model; $(touch BAD)'
        runtime = Runtime(self.root, model=model, executor=lambda c,p,d: seen.append(c) or "ok")
        runtime.generate(["task"], {}, "original")
        command = seen[0]
        self.assertEqual(command[command.index("--model") + 1], model)
        self.assertIn("--ephemeral", command)
        self.assertIn("read-only", command)
        self.assertNotIn("resume", command)

    def test_pdf_context_is_preserved_as_text_and_all_page_images(self):
        import pymupdf
        doc = pymupdf.open()
        for label in ["PAGE ONE TRUTH", "PAGE TWO TRUTH"]:
            page = doc.new_page()
            page.insert_text((72,72), label)
        data = doc.tobytes()
        doc.close()
        seen = []
        runtime = Runtime(self.root, executor=lambda c,p,d: seen.append((c,p)) or "ok")
        runtime.generate([types.Part.from_bytes(data=data, mime_type="application/pdf"), "task"], {}, "original")
        command, prompt = seen[0]
        self.assertIn("PAGE ONE TRUTH", prompt)
        self.assertIn("PAGE TWO TRUTH", prompt)
        self.assertEqual(command.count("--image"), 2)
        self.assertEqual(len(list(self.root.glob("invocations/*/attachment-*.pdf"))), 1)

    def test_missing_image_tool_is_explicit_capability_failure(self):
        runtime = Runtime(self.root)
        with self.assertRaisesRegex(CapabilityError, "image-tool"):
            runtime.generate(["diagram"], {"response_modalities": ["IMAGE"]}, "original-image")
        self.assertTrue(runtime.fatal)

    def test_image_tool_handoff_is_separate_process_with_real_image_bytes(self):
        fixture = self.root / "image_fixture.py"
        fixture.write_text('import json,sys\nfrom PIL import Image\n'
                           'request=json.load(open(sys.argv[1]))\n'
                           'Image.new("RGB",(16,16),"white").save(request["output_path"])\n')
        runtime = Runtime(self.root / "execution", image_command=[sys.executable, str(fixture)])
        result = runtime.generate(["diagram fixture"], {"response_modalities": ["IMAGE"]}, "original-image")
        self.assertTrue(result.candidates[0].content.parts[0].inline_data.data.startswith(b"\x89PNG"))
        self.assertEqual(self.events(runtime)[-1]["event"], "image_end")

    def test_failed_configured_image_tool_is_fatal_after_five_original_attempts(self):
        runtime = Runtime(self.root, image_command=[sys.executable, "-c", "raise SystemExit(4)"])
        configure(runtime)
        with patch("utils.gemini_utils.time.sleep"):
            with self.assertRaisesRegex(CapabilityError, "exhausted"):
                generate_image_with_gemini("original-image", "diagram")
        self.assertEqual(sum(e["event"] == "image_start" for e in self.events(runtime)), 5)
        self.assertTrue(runtime.fatal)

    def test_missing_inputs_fail_before_paid_probe_and_create_no_running_manifest(self):
        run = VENDOR.parent / "scripts" / "run.py"
        output = self.root / "should-not-exist"
        result = subprocess.run([sys.executable, str(run), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("required", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
