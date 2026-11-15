"""Vibe configuration and media boundaries; no live model calls."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "paper-orchestra/vendor"
sys.path.insert(0, str(VENDOR))
import orchestra_vibe as vibe


# A labelled protocol fixture, not Vibe or a real model. It exercises the actual
# subprocess/JSON-RPC driver and native-proof inspector without paid execution.
ACP_FIXTURE = r'''
import json, os, sys, uuid, time
session = "labelled-vibe-fixture-" + uuid.uuid4().hex
def emit(value):
    print(json.dumps(value), flush=True)
def update(value):
    emit({"jsonrpc":"2.0", "method":"session/update", "params":{"sessionId":session, "update":value}})
for line in sys.stdin:
    message = json.loads(line)
    method, number = message.get("method"), message.get("id")
    if not method:
        continue
    with open("fixture-methods.txt", "a") as out:
        out.write(method + "\n")
    if method == "initialize":
        result = {"protocolVersion":1, "agentCapabilities":{"promptCapabilities":{"image":True}, "sessionCapabilities":{"close":{}}}}
    elif method == "session/new":
        model = os.environ.get("FIXTURE_MODEL_OVERRIDE", os.environ.get("VIBE_ACTIVE_MODEL", "fixture-native-default"))
        settings = json.loads(os.environ.get("VIBE_MODELS", "{}"))
        thinking = os.environ.get("FIXTURE_EFFORT_OVERRIDE", settings.get(model, {}).get("thinking", "high"))
        result = {"sessionId":session,"configOptions":[{"id":"model","currentValue":model,"type":"select","options":[{"value":model,"name":model}]},{"id":"thinking","currentValue":thinking,"type":"select","options":[{"value":thinking,"name":thinking}]}]}
    elif method == "session/prompt":
        if os.environ.get("FIXTURE_TIMEOUT"):
            time.sleep(30)
        if os.environ.get("FIXTURE_NARRATION"):
            update({"sessionUpdate":"agent_message_chunk","messageId":"fixture-pre-search-message","content":{"type":"text","text":"LABELLED PRE-SEARCH NARRATION, NOT THE ROLE ARTIFACT"}})
        search = "web_search" in json.loads(os.environ.get("VIBE_ENABLED_TOOLS", "[]"))
        if search and os.environ.get("FIXTURE_CATALOG_LOOKUP"):
            update({"sessionUpdate":"tool_call","toolCallId":"effect-tool-discovery-fixture","title":"Searching for relevant tools","kind":"other","status":"completed","rawInput":{"mode":"best_match"},"rawOutput":{"mode":"best_match","toolCount":0,"connectorNoticeCount":0},"_meta":{"tool_name":"search_tool_functions","effect_kind":"tool"}})
        if search and not os.environ.get("FIXTURE_NO_SEARCH") or os.environ.get("FIXTURE_FORBIDDEN_TOOL"):
            name = "bash" if os.environ.get("FIXTURE_FORBIDDEN_TOOL") else "connector_web_search.web_search" if os.environ.get("FIXTURE_CONNECTOR_SEARCH") else "web_search"
            update({"sessionUpdate":"tool_call","toolCallId":"fixture-search","kind":"search","status":"in_progress","_meta":{"tool_name":name},"rawInput":{"query":"labelled fixture query"}})
            emit({"jsonrpc":"2.0","id":"fixture-permission","method":"session/request_permission","params":{"sessionId":session,"toolCall":{"toolCallId":"fixture-search","_meta":{"tool_name":name}},"options":[{"kind":"allow_once","optionId":"once","name":"Allow once"},{"kind":"reject_once","optionId":"deny","name":"Deny"}]}})
            permission = json.loads(sys.stdin.readline())
            if permission.get("result", {}).get("outcome", {}).get("optionId") != "once":
                raise SystemExit(7)
            status = "failed" if os.environ.get("FIXTURE_SEARCH_ERROR") else "completed"
            output = {"isError":True,"error":"labelled fixture search failure"} if status == "failed" else {"query":"labelled fixture query","answer":"labelled result","sources":[{"title":"fixture primary","url":"https://example.invalid/fixture"}]}
            update({"sessionUpdate":"tool_call_update","toolCallId":"fixture-search","status":status,"_meta":{"tool_name":name},"rawOutput":output})
        update({"sessionUpdate":"agent_message_chunk","messageId":"fixture-final-answer","content":{"type":"text","text":"{\"fixture\":true}"}})
        result = {"stopReason":"end_turn"}
    elif method == "session/close":
        result = {}
    else:
        raise SystemExit("Fixture rejects unexpected method " + method)
    emit({"jsonrpc":"2.0","id":number,"result":result})
'''


class VibePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def plan(self, model="mistral-large-4-0", effort="high", images=(), search=False):
        return vibe.prepare({"backend":"mistral-vibe", "model":model, "effort":effort},
                            "LABELLED ORIGINAL ROLE PROMPT", list(images), search,
                            self.directory)

    def image(self, name="page-1.png"):
        target = self.directory / name
        target.write_bytes(b"labelled-native-image-fixture")
        return str(target)

    def test_real_vibe_acp_command_without_resume_or_setters(self):
        plan = self.plan()
        self.assertEqual(plan["command"], ["vibe-acp"])
        self.assertEqual(plan["mode"], "acp")
        self.assertEqual(plan["stdin"], "LABELLED ORIGINAL ROLE PROMPT")
        self.assertEqual(plan["acp"]["config_strategy"], "preconfigured")
        self.assertNotIn("--effort", plan["command"])
        self.assertNotIn("--resume", plan["command"])

    def test_model_and_effort_are_native_per_process_config(self):
        plan = self.plan()
        self.assertEqual(plan["env"]["VIBE_ACTIVE_MODEL"], "mistral-large-4-0")
        preset = json.loads(plan["env"]["VIBE_MODELS"])["mistral-large-4-0"]
        self.assertEqual(preset["provider"], "mistral")
        self.assertEqual(preset["name"], "mistral-large-4-0")
        self.assertEqual(preset["thinking"], "high")
        self.assertEqual(preset["thinking_levels"], ["low", "medium", "high"])
        self.assertTrue(preset["supports_images"])

    def test_no_auth_environment_or_user_home_is_copied(self):
        before = dict(os.environ)
        with patch.dict(os.environ, {"MISTRAL_API_KEY":"fixture-secret-not-for-evidence",
                                     "VIBE_HOME":"/private/fixture-native-home"}):
            plan = self.plan()
            self.assertNotIn("MISTRAL_API_KEY", plan["env"])
            self.assertNotIn("VIBE_HOME", plan["env"])
            self.assertNotIn("fixture-secret-not-for-evidence", json.dumps(plan))
        self.assertEqual(dict(os.environ), before)

    def test_only_discovery_enables_native_web_search(self):
        plan = self.plan(search=True)
        self.assertEqual(json.loads(plan["env"]["VIBE_ENABLED_TOOLS"]),
                         ["web_search", "connector_web_search_web_search"])
        self.assertEqual(json.loads(plan["env"]["VIBE_DISABLED_TOOLS"]), [])
        self.assertEqual(plan["acp"]["allowed_search_tools"],
                         ["web_search", "connector_web_search.web_search"])
        self.assertEqual(plan["acp"]["allowed_auxiliary_tools"], ["search_tool_functions"])
        self.assertEqual(json.loads(plan["env"]["VIBE_CONNECTORS"]),
                         [{"name":"web_search", "disabled":False, "disabled_tools":[]}])
        ordinary = self.plan()
        self.assertEqual(json.loads(ordinary["env"]["VIBE_DISABLED_TOOLS"]), ["*"])
        self.assertEqual(ordinary["acp"]["allowed_search_tools"], [])
        self.assertEqual(ordinary["acp"]["allowed_auxiliary_tools"], [])
        self.assertEqual(ordinary["env"]["VIBE_ENABLE_CONNECTORS"], "false")

    def test_subagents_skills_project_context_titles_and_extra_output_retries_disabled(self):
        env = self.plan()["env"]
        self.assertEqual(env["VIBE_DEFAULT_AGENT"], "ask")
        self.assertEqual(json.loads(env["VIBE_ENABLED_AGENTS"]), ["ask"])
        for key in ["VIBE_ENABLE_SUBAGENTS", "VIBE_ENABLE_MCP", "VIBE_INCLUDE_PROJECT_CONTEXT",
                    "VIBE_SESSION_LOGGING__ENABLED", "VIBE_SESSION_LOGGING__GENERATE_TITLES"]:
            self.assertEqual(env[key], "false")
        self.assertEqual(json.loads(env["VIBE_DISABLED_SKILLS"]), ["*"])
        self.assertEqual(env["VIBE_OUTSIDE_WORKDIR"], "deny")
        self.assertEqual(env["VIBE_OUTPUT_LIMIT_RETRIES"], "0")

    def test_direct_images_are_retained_in_order(self):
        images = [self.image("page-1.png"), self.image("page-2.png")]
        plan = self.plan(images=images)
        self.assertEqual(plan["images"], [str(Path(path).resolve()) for path in images])
        self.assertEqual(plan["acp"]["image_limit"], 8)
        self.assertEqual(plan["acp"]["image_max_bytes"], 10 * 1024 * 1024)

    def test_exceeding_native_image_count_fails_without_truncation(self):
        with self.assertRaisesRegex(ValueError, "No pages were truncated"):
            self.plan(images=[self.image()] * 9)

    def test_exceeding_native_image_size_fails_before_dispatch(self):
        image = self.directory / "large.png"
        with image.open("wb") as output:
            output.truncate(vibe.IMAGE_MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "10 MiB"):
            self.plan(images=[str(image)])

    def test_unknown_or_default_image_model_cannot_trigger_vision_substitution(self):
        image = self.image()
        for model in [None, "custom-native-alias"]:
            with self.subTest(model=model), self.assertRaisesRegex(ValueError, "vision helper"):
                self.plan(model=model, effort=None, images=[image])

    def test_known_model_effort_levels_do_not_share_a_universal_scale(self):
        for model, effort in [("mistral-large-4-0", "max"),
                              ("mistral-large-4", "off"),
                              ("mistral-small-2603", "medium")]:
            with self.subTest(model=model, effort=effort), self.assertRaisesRegex(ValueError, "supports thinking"):
                self.plan(model=model, effort=effort)
        self.assertEqual(self.plan(model="mistral-small-2603", effort="off")["acp"]["effort"], "off")

    def test_mistral_hosted_glm_is_distinct_from_multimodal_glm_flash(self):
        text = self.plan(model="zai-glm-5-3", effort="max")
        preset = json.loads(text["env"]["VIBE_MODELS"])["zai-glm-5-3"]
        self.assertEqual(preset["name"], "zai-glm-5-3")
        self.assertEqual(preset["provider"], "mistral")
        self.assertEqual(preset["thinking_levels"], ["low", "high", "max"])
        self.assertFalse(preset["supports_images"])
        with self.assertRaisesRegex(ValueError, "text-only"):
            self.plan(model="zai-glm-5-3", effort="high", images=[self.image()])
        flash = self.plan(model="zai-glm-5-3-flash", effort="high", images=[self.image()])
        self.assertTrue(json.loads(flash["env"]["VIBE_MODELS"])["zai-glm-5-3-flash"]["supports_images"])

    def test_glm_effort_rejects_none_off_medium_and_xhigh(self):
        for model in ["zai-glm-5-3", "zai-glm-5-3-flash"]:
            for effort in ["none", "off", "medium", "xhigh"]:
                with self.subTest(model=model, effort=effort), self.assertRaisesRegex(ValueError, "supports thinking"):
                    self.plan(model=model, effort=effort)

    def test_explicit_effort_needs_a_model_to_avoid_global_default_write(self):
        with self.assertRaisesRegex(ValueError, "explicit model/alias"):
            self.plan(model=None, effort="high")

    def test_null_model_and_effort_inherit_native_config_for_text(self):
        plan = self.plan(model=None, effort=None)
        self.assertNotIn("VIBE_ACTIVE_MODEL", plan["env"])
        self.assertNotIn("VIBE_MODELS", plan["env"])
        self.assertIsNone(plan["acp"]["model"])
        self.assertIsNone(plan["acp"]["effort"])

    def test_unknown_text_alias_keeps_configured_provider(self):
        plan = self.plan(model="my-configured-native-alias", effort="high")
        self.assertEqual(json.loads(plan["env"]["VIBE_MODELS"]),
                         {"my-configured-native-alias":{"thinking":"high"}})


class VibeWireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.fixture = self.root / "labelled-vibe-acp-fixture.py"
        self.fixture.write_text(ACP_FIXTURE)

    def dispatch(self, name="attempt", *, search=False, image=False, overrides=None, timeout=5):
        directory = self.root / name
        directory.mkdir()
        images = []
        if image:
            target = directory / "attachment.png"
            target.write_bytes(b"labelled full image byte fixture")
            images = [str(target)]
        prompt = "LABELLED INDEPENDENT ROLE TASK WITH ITS ORIGINAL INPUTS"
        (directory / "prompt.txt").write_text(prompt)
        selection = {"backend":"mistral-vibe", "model":"mistral-large-4-0", "effort":"high"}
        plan = vibe.prepare(selection, prompt, images, search, directory)
        plan["command"] = [sys.executable, str(self.fixture)]
        plan["env"].update(overrides or {})
        path = directory / "transport.json"
        path.write_text(json.dumps(plan, indent=2))
        request = {"backend":"mistral-vibe", "model_routing":selection,
                   "transport_plan_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                   "images":images, "image_sha256":{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in images},
                   "search_required":search}
        pids = []
        response = vibe.execute(plan, directory, timeout, pids.append)
        return directory, request, response, pids

    def test_separate_subprocesses_have_native_unique_sessions_and_no_resume(self):
        first, request_a, response_a, pids_a = self.dispatch("first", image=True)
        second, request_b, response_b, pids_b = self.dispatch("second")
        a, b = vibe.inspect(first, request_a), vibe.inspect(second, request_b)
        self.assertTrue(a["completed"], a["errors"])
        self.assertTrue(b["completed"], b["errors"])
        self.assertNotEqual(a["sessions"], b["sessions"])
        self.assertNotEqual(pids_a, pids_b)
        self.assertEqual(response_a, '{"fixture":true}')
        self.assertEqual(response_b, response_a)
        self.assertEqual(a["images_delivered"], request_a["images"])
        self.assertEqual(a["observed_effort"], "high")
        self.assertEqual((first / "fixture-methods.txt").read_text().splitlines(),
                         ["initialize", "session/new", "session/prompt", "session/close"])

    def test_native_search_permission_and_completed_result_are_independent_proof(self):
        directory, request, _, _ = self.dispatch(search=True)
        receipt = vibe.inspect(directory, request)
        self.assertTrue(receipt["completed"], receipt["errors"])
        self.assertTrue(receipt["searched"])
        records = [json.loads(line) for line in (directory / "acp-wire.jsonl").read_text().splitlines()]
        permissions = [row["message"] for row in records if row["direction"] == "send" and row["message"].get("id") == "fixture-permission"]
        self.assertEqual(permissions[0]["result"]["outcome"]["optionId"], "once")

    def test_last_native_assistant_message_is_the_artifact_not_search_narration(self):
        directory, request, response, _ = self.dispatch(search=True, overrides={"FIXTURE_NARRATION":"1"})
        self.assertEqual(response, '{"fixture":true}')
        receipt = vibe.inspect(directory, request)
        self.assertTrue(receipt["completed"], receipt["errors"])
        self.assertEqual(receipt["response"], response)
        self.assertIn("LABELLED PRE-SEARCH NARRATION", (directory / "events.jsonl").read_text())

    def test_real_vibe_catalog_lookup_then_exact_connector_route_search(self):
        directory, request, response, _ = self.dispatch(search=True, overrides={
            "FIXTURE_CATALOG_LOOKUP":"1", "FIXTURE_CONNECTOR_SEARCH":"1"})
        receipt = vibe.inspect(directory, request)
        self.assertTrue(receipt["completed"], receipt["errors"])
        self.assertTrue(receipt["searched"])
        self.assertEqual(receipt["response"], response)
        self.assertIn("connector_web_search.web_search", (directory / "events.jsonl").read_text())

    def test_native_catalog_lookup_alone_never_proves_live_search(self):
        directory, request, _, _ = self.dispatch(search=True, overrides={
            "FIXTURE_CATALOG_LOOKUP":"1", "FIXTURE_NO_SEARCH":"1"})
        receipt = vibe.inspect(directory, request)
        self.assertFalse(receipt["searched"])
        self.assertTrue(receipt["failed"])
        self.assertTrue(any("completed native search" in error for error in receipt["errors"]))

    def test_failed_search_does_not_satisfy_discovery(self):
        directory, request, _, _ = self.dispatch(search=True, overrides={"FIXTURE_SEARCH_ERROR":"1"})
        receipt = vibe.inspect(directory, request)
        self.assertTrue(receipt["failed"])
        self.assertFalse(receipt["searched"])

    def test_missing_search_cannot_be_replaced_by_a_completed_answer(self):
        directory, request, response, _ = self.dispatch(search=True, overrides={"FIXTURE_NO_SEARCH":"1"})
        self.assertTrue(response)
        receipt = vibe.inspect(directory, request)
        self.assertTrue(receipt["failed"])
        self.assertFalse(receipt["searched"])

    def test_native_model_and_effort_mismatch_stop_before_prompt(self):
        for key in ["FIXTURE_MODEL_OVERRIDE", "FIXTURE_EFFORT_OVERRIDE"]:
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "differs from selected"):
                self.dispatch(key, overrides={key:"different-fixture-value"})
            self.assertNotIn("session/prompt", (self.root / key / "fixture-methods.txt").read_text())

    def test_unapproved_native_tool_ends_attempt(self):
        with self.assertRaisesRegex(RuntimeError, "disallowed tool"):
            self.dispatch(overrides={"FIXTURE_FORBIDDEN_TOOL":"1"})
        outcome = json.loads((self.root / "attempt/acp-exit.json").read_text())
        self.assertFalse(outcome["completed_turn"])

    def test_native_timeout_is_failed_attempt_without_completion_receipt(self):
        with self.assertRaises(TimeoutError):
            self.dispatch(overrides={"FIXTURE_TIMEOUT":"1"}, timeout=.15)
        outcome = json.loads((self.root / "attempt/acp-exit.json").read_text())
        self.assertFalse(outcome["completed_turn"])
        self.assertIsNotNone(outcome["returncode"])

    def test_auditor_rejects_changed_image_bytes(self):
        directory, request, _, _ = self.dispatch(image=True)
        Path(request["images"][0]).write_bytes(b"different image bytes")
        receipt = vibe.inspect(directory, request)
        self.assertTrue(receipt["failed"])
        self.assertTrue(any("image" in error for error in receipt["errors"]))


if __name__ == "__main__":
    unittest.main()
