"""Native failure/effort/media guards; all responses are labelled fixtures."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "paper-orchestra/vendor"))
from orchestra_execution import execution_policy
from orchestra_runtime import Runtime, configure
import orchestra_runtime
from orchestra_transports import prepare_invocation, inspect_invocation, validate_invocation_plan
from utils.gemini_utils import call_gemini_with_contents
from tests.test_multiruntime_audit import claude_events, write_events


class NativeGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="native-guard-fixtures-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.request = {"backend":"claude-code", "search_required":False, "images":[],
                        "model_routing":{"model":"claude-labelled-fixture", "effort":"high"}}

    def inspect(self, events):
        write_events(self.root,events)
        return inspect_invocation(self.root,self.request)

    def test_native_400_uses_original_nonretryable_rule_without_echoing_error_body(self):
        calls = []
        def fixture(command,prompt,directory):
            calls.append(directory)
            events = claude_events("labelled-session", "", failed=True)
            events[-1]["errors"] = ["API Error: 400 invalid input; LABELLED_SECRET_MUST_NOT_BE_ECHOED"]
            write_events(directory,events)
            return ""
        previous = orchestra_runtime._runtime
        self.addCleanup(configure,previous)
        configure(Runtime(self.root / "execution",backend="claude-code",model="claude-labelled-fixture",effort="high",executor=fixture))
        with patch("utils.gemini_utils.time.sleep") as sleep, self.assertRaisesRegex(RuntimeError,"400") as raised:
            call_gemini_with_contents(["LABELLED INPUT FIXTURE"],"upstream-fixture")
        self.assertEqual(len(calls),1)
        sleep.assert_not_called()
        self.assertNotIn("LABELLED_SECRET",str(raised.exception))

    def test_native_tool_outside_role_policy_cannot_count_as_success(self):
        events = claude_events("labelled-session","fixture")
        events.insert(1,{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"labelled-tool"}]}})
        result = self.inspect(events)
        self.assertFalse(result["completed"])
        self.assertTrue(any("outside" in x for x in result["errors"]))

    def test_echoed_effort_drift_is_rejected(self):
        events = claude_events("labelled-session","fixture")
        events[0]["effort"] = "medium"
        result = self.inspect(events)
        self.assertFalse(result["completed"])
        self.assertTrue(any("different effort" in x for x in result["errors"]))

    def test_inline_native_image_substitution_is_rejected(self):
        image = self.root / "fixture.png"
        image.write_bytes(b"LABELLED IMAGE BYTES")
        prompt = "LABELLED ORIGINAL PROMPT"
        (self.root / "prompt.txt").write_text(prompt)
        self.request.update(images=[str(image)],image_sha256={str(image):hashlib.sha256(image.read_bytes()).hexdigest()})
        plan = prepare_invocation(self.request["model_routing"] | {"backend":"claude-code"},prompt,[str(image)],False,self.root)
        payload = json.loads(plan["stdin"])
        payload["message"]["content"][1]["source"]["data"] = base64.b64encode(b"DIFFERENT LABELLED IMAGE").decode()
        plan["stdin"] = json.dumps(payload)
        (self.root / "transport.json").write_text(json.dumps(plan))
        result = self.inspect(claude_events("labelled-session","fixture"))
        self.assertFalse(result["completed"])
        self.assertTrue(any("image bytes differ" in x for x in result["errors"]))

    def test_transport_plan_preserves_external_metadata_line_endings(self):
        prompt = "First line\r\nSecond line\nThird line\rlast line with café"
        path = self.root / "prompt.txt"
        for backend in ("codex", "claude-code", "antigravity", "mistral-vibe"):
            with self.subTest(backend=backend):
                selection = {"backend": backend, "model": None, "effort": None}
                plan = prepare_invocation(selection, prompt, [], False, self.root)
                data = json.dumps(plan).encode("utf-8")
                (self.root / "transport.json").write_bytes(data)
                request = {"backend": backend, "search_required": False,
                           "transport_plan_sha256": hashlib.sha256(data).hexdigest()}
                path.write_bytes(prompt.encode("utf-8"))
                self.assertEqual(validate_invocation_plan(self.root, request, plan["command"], selection), [])
                path.write_bytes(prompt.replace("\r\n", "\n").encode("utf-8"))
                self.assertTrue(validate_invocation_plan(self.root, request, plan["command"], selection))

    def test_known_model_effort_incompatibility_fails_during_policy_resolution(self):
        for model,effort in [("mistral-large-4","max"),("mistral-small-2603","medium"),("zai-glm-5-3","medium")]:
            with self.subTest(model=model), self.assertRaises(ValueError):
                execution_policy(profile={"schema_version":2,"default":{"backend":"mistral-vibe","model":model,"effort":effort}})


if __name__ == "__main__":
    unittest.main()
