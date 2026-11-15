"""Native recording/response boundaries using labelled fixtures, never inference.

The one subprocess below is the Python interpreter emitting fixture JSONL. It
does not invoke a model, native agent CLI, network, R, or TeX compiler.
"""
from __future__ import annotations

import base64
from contextlib import redirect_stdout, redirect_stderr
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper-orchestra/vendor"))
import orchestra_transports as transports
import orchestra_runtime as runtime_module
from orchestra_runtime import Runtime, configure, role_override
from orchestra_models import audit_model_policy
from utils.gemini_utils import call_gemini_with_contents
from tests import test_trace_audit as trace_fixtures
from tests import test_provenance_audit as provenance_fixtures
from tests import test_antigravity_transport as acp_fixtures


def claude_events(session, response, *, search=False, failed=False):
    """Labelled native stream fixtures, not proof of any actual model run."""
    events = [{"type": "system", "subtype": "init", "session_id": session,
               "model": "claude-labelled-fixture", "effort": "high"}]
    if search:
        events += [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "WebSearch", "id": "labelled-search-1", "input": {"query": "fixture query"}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "labelled-search-1", "content": "labelled result evidence", "is_error": False}]}},
        ]
    events.append({"type": "result", "subtype": "error_during_execution" if failed else "success",
                   "session_id": session, "is_error": failed, "result": response})
    return events


def write_events(directory, events):
    # JSONL means physical LF; Unicode NEL inside JSON strings remains data.
    (directory / "events.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))


class NativeTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="labelled-native-transport-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.request = {"backend": "claude-code", "images": [],
                        "model_routing": {"model": "claude-labelled-fixture", "effort": "high"}}

    def inspect(self, events, request=None):
        write_events(self.directory, events)
        return transports.inspect_invocation(self.directory, request or self.request)

    def test_native_success_response_session_model_and_search_are_recomputed(self):
        response = '{"labelled_fixture":"native\u0085response"}'
        result = self.inspect(claude_events("labelled-session", response, search=True))
        self.assertTrue(result["completed"], result)
        self.assertFalse(result["failed"], result)
        self.assertEqual(result["sessions"], ["labelled-session"])
        self.assertEqual(result["response"], response)
        self.assertEqual(result["observed_model"], "claude-labelled-fixture")
        self.assertEqual(result["observed_effort"], "high")
        self.assertTrue(result["searched"])

    def test_prose_cannot_substitute_for_an_executed_native_search(self):
        result = self.inspect(claude_events("labelled-session", "I used WebSearch successfully"))
        self.assertTrue(result["completed"])
        self.assertFalse(result["searched"])

    def test_search_requires_matching_completed_nonerror_tool_result(self):
        for alteration in ("missing", "failed", "unrelated"):
            with self.subTest(alteration=alteration):
                events = claude_events("labelled-session", "fixture", search=True)
                if alteration == "missing":
                    events.pop(2)
                else:
                    block = events[2]["message"]["content"][0]
                    block["is_error" if alteration == "failed" else "tool_use_id"] = True if alteration == "failed" else "other-id"
                self.assertFalse(self.inspect(events)["searched"])

    def test_search_requires_real_nonempty_tool_call_identifiers(self):
        events = claude_events("labelled-session", "fixture", search=True)
        events[1]["message"]["content"][0].pop("id")
        events[2]["message"]["content"][0].pop("tool_use_id")
        self.assertFalse(self.inspect(events)["searched"])

    def test_native_failure_or_mismatched_session_or_duplicate_init_cannot_succeed(self):
        cases = []
        cases.append(claude_events("labelled-session", "fixture", failed=True))
        mismatch = claude_events("labelled-session", "fixture")
        mismatch[-1]["session_id"] = "other-session"
        cases.append(mismatch)
        duplicate = claude_events("labelled-session", "fixture")
        duplicate.insert(1, copy.deepcopy(duplicate[0]))
        cases.append(duplicate)
        error = claude_events("labelled-session", "fixture")
        error.insert(1, {"type": "error", "error": {"message": "labelled fixture failure"}})
        cases.append(error)
        for events in cases:
            with self.subTest(events=events):
                result = self.inspect(events)
                self.assertFalse(result["completed"], result)
                self.assertTrue(result["failed"])
                self.assertTrue(result["errors"])

    def test_native_full_model_id_mismatch_is_rejected(self):
        events = claude_events("labelled-session", "fixture")
        events[0]["model"] = "claude-other-fixture"
        result = self.inspect(events)
        self.assertFalse(result["completed"])
        self.assertTrue(any("different model" in error for error in result["errors"]))

    def test_normalized_receipt_cannot_replace_missing_native_events(self):
        (self.directory / "receipt.json").write_text(json.dumps({"completed": True, "searched": True, "response": "fixture"}))
        result = self.inspect([])
        self.assertFalse(result["completed"])
        self.assertFalse(result["searched"])

    def test_claude_uses_native_effort_and_exact_image_bytes_in_fresh_session(self):
        image = self.directory / "page.png"
        image.write_bytes(b"LABELLED PNG INPUT FIXTURE")
        selection = {"backend": "claude-code", "model": "claude-labelled-fixture", "effort": "high"}
        first = transports.prepare_invocation(selection, "ORIGINAL PROMPT FIXTURE", [str(image)], True, self.directory)
        second = transports.prepare_invocation(selection, "ORIGINAL PROMPT FIXTURE", [str(image)], True, self.directory)
        command = first["command"]
        self.assertEqual(command[0], "claude")
        self.assertNotIn("--resume", command)
        self.assertNotIn("--continue", command)
        self.assertIn("--no-session-persistence", command)
        self.assertEqual(command[command.index("--effort") + 1], "high")
        self.assertEqual(command[command.index("--model") + 1], selection["model"])
        self.assertNotEqual(command[command.index("--session-id") + 1], second["command"][second["command"].index("--session-id") + 1])
        content = json.loads(first["stdin"])["message"]["content"]
        self.assertEqual(content[0], {"type": "text", "text": "ORIGINAL PROMPT FIXTURE"})
        self.assertEqual(base64.b64decode(content[1]["source"]["data"]), image.read_bytes())
        self.assertEqual(command[command.index("--tools") + 1], "WebSearch")
        ordinary = transports.prepare_invocation(selection, "fixture", [], False, self.directory)
        self.assertEqual(ordinary["command"][ordinary["command"].index("--tools") + 1], "")

    def test_codex_effort_is_native_config_and_null_keeps_runtime_default(self):
        selection = {"backend": "codex", "model": "codex-labelled-fixture", "effort": "xhigh"}
        plan = transports.prepare_invocation(selection, "fixture", [], False, self.directory)
        self.assertEqual(plan["command"][0], "codex")
        self.assertIn('model_reasoning_effort="xhigh"', plan["command"])
        self.assertEqual(plan["stdin"], "fixture")
        ordinary = transports.prepare_invocation({"backend": "codex", "model": None, "effort": None}, "fixture", [], False, self.directory)
        self.assertNotIn("--model", ordinary["command"])
        self.assertFalse(any("model_reasoning_effort" in item for item in ordinary["command"]))

    def test_python_fixture_process_retains_native_events_and_pid_without_a_model(self):
        events = claude_events("labelled-subprocess-session", "LABELLED SUBPROCESS RESPONSE")
        self.directory.joinpath("request.json").write_text(json.dumps(self.request))
        script = "import json; events=" + repr(events) + "; [print(json.dumps(e)) for e in events]"
        plan = {"backend": "claude-code", "command": [sys.executable, "-c", script], "stdin": "fixture", "env": {}}
        pids = []
        response = transports.execute_invocation(plan, self.directory, 10, pids.append)
        self.assertEqual(response, "LABELLED SUBPROCESS RESPONSE")
        self.assertEqual(len(pids), 1)
        self.assertIsInstance(pids[0], int)
        self.assertEqual(transports.read_events(self.directory / "events.jsonl"), events)


class NativeRuntimeHandoffTests(unittest.TestCase):
    """Exercise the real runtime/original parsers with labelled executor results."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="labelled-native-runtime-")
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(configure, runtime_module._runtime)
        self.root = Path(self.tmp.name)

    def execute_as(self, role, config=None, contents=None):
        token = role_override.set(role)
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return call_gemini_with_contents(contents or ["ORIGINAL LABELLED TASK INPUT"], "upstream-fixture", **(config or {}))
        finally:
            role_override.reset(token)

    def test_native_roles_keep_fresh_inputs_json_handoffs_model_and_effort(self):
        seen = []
        response = '{"labelled_fixture":true,"payload":[1,2,3]}'
        def executor(command, prompt, directory):
            request = json.loads((directory / "request.json").read_text())
            seen.append((command, prompt, directory, request))
            if request["backend"] == "claude-code":
                write_events(directory, claude_events(directory.name, response))
            return response
        runtime = Runtime(self.root / "execution", executor=executor,
                          model_profile={"schema_version": 2, "groups": {
                              "writing": {"backend": "claude-code", "model": "claude-labelled-fixture", "effort": "high"}}})
        configure(runtime)
        for role in ("outline", "section-writer"):
            result = self.execute_as(role)
            self.assertEqual(result["raw_response"], response)
            self.assertEqual(result["parsed_response"], json.loads(response))
        self.assertEqual(len({directory for command, prompt, directory, request in seen}), 2)
        self.assertEqual(len(runtime.sessions), 2)
        for command, prompt, directory, request in seen:
            self.assertEqual(command[0], "claude")
            self.assertIn("ORIGINAL LABELLED TASK INPUT", prompt)
            self.assertEqual(request["backend"], "claude-code")
            self.assertEqual(request["model_routing"]["effort"], "high")
            self.assertEqual(request["model_routing"]["model"], "claude-labelled-fixture")
            self.assertEqual((directory / "response.txt").read_text(), response)
            self.assertEqual(hashlib.sha256((directory / "transport.json").read_bytes()).hexdigest(), request["transport_plan_sha256"])
        parsed = list((runtime.root / "parsed").glob("*.json"))
        self.assertEqual(len(parsed), 2)
        self.assertTrue(all(json.loads(path.read_text()) == json.loads(response) for path in parsed))

    def test_original_five_parse_retries_keep_native_selection_and_fresh_sessions(self):
        seen = []
        def executor(command, prompt, directory):
            request = json.loads((directory / "request.json").read_text())
            seen.append((command, directory, request))
            response = "LABELLED INVALID JSON RESPONSE"
            write_events(directory, claude_events(directory.name, response))
            return response
        runtime = Runtime(self.root / "execution", executor=executor, backend="claude-code", model="claude-labelled-fixture", effort="high")
        configure(runtime)
        with patch("utils.gemini_utils.time.sleep"), self.assertRaises(AssertionError):
            self.execute_as("peer-reviewer")
        self.assertEqual(len(seen), 5)
        self.assertEqual(len({directory for command, directory, request in seen}), 5)
        self.assertEqual(len(runtime.sessions), 5)
        self.assertEqual({(request["backend"], request["model_routing"]["model"], request["model_routing"]["effort"])
                          for command, directory, request in seen}, {("claude-code", "claude-labelled-fixture", "high")})
        self.assertTrue(all(command[command.index("--effort") + 1] == "high" for command, directory, request in seen))

    def test_native_return_string_without_native_evidence_is_not_accepted(self):
        runtime = Runtime(self.root / "execution", executor=lambda *args: '{"labelled_fixture":true}', backend="claude-code")
        with self.assertRaisesRegex(RuntimeError, "independent session evidence"):
            runtime.generate(["LABELLED INPUT"], {}, "u")

    def test_native_image_payload_keeps_every_attachment_byte(self):
        seen = []
        def executor(command, prompt, directory):
            request = json.loads((directory / "request.json").read_text())
            seen.append((request, json.loads((directory / "transport.json").read_text())))
            response = '{"labelled_fixture":true}'
            write_events(directory, claude_events(directory.name, response))
            return response
        runtime = Runtime(self.root / "execution", executor=executor, backend="claude-code")
        images = [b"LABELLED FIRST PAGE PNG", b"LABELLED SECOND PAGE PNG"]
        parts = [SimpleNamespace(inline_data=SimpleNamespace(mime_type="image/png", data=data)) for data in images]
        runtime.generate(["ORIGINAL FIGURE CONTEXT", *parts], {}, "u")
        request, plan = seen[0]
        payload = json.loads(plan["stdin"])["message"]["content"]
        self.assertEqual([base64.b64decode(item["source"]["data"]) for item in payload if item["type"] == "image"], images)
        self.assertEqual([Path(path).read_bytes() for path in request["images"]], images)
        self.assertEqual(len(request["media"]), 2)


class NativeManuscriptAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = provenance_fixtures.ProvenanceAuditTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for number, call in enumerate(self.fixture.calls):
            directory = call["directory"]
            request = json.loads((directory / "request.json").read_text())
            request["backend"] = "claude-code"
            request["model_routing"] = {"model": "claude-labelled-fixture", "effort": "high"}
            (directory / "request.json").write_text(json.dumps(request))
            call["start"]["backend"] = "claude-code"
            write_events(directory, claude_events(f"labelled-manuscript-session-{number}", (directory / "response.txt").read_text()))

    def test_native_raw_to_original_parse_effective_compile_and_pdf_handoffs_pass(self):
        summary, errors = self.fixture.audit()
        self.assertEqual(errors, [])
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["manuscript_results_checked"], 3)
        self.assertEqual(len(summary["compiled_manuscripts"]), 3)

    def test_native_final_text_tamper_cannot_be_hidden_by_retained_parse_or_receipt(self):
        call = self.fixture.calls[1]
        write_events(call["directory"], claude_events("labelled-manuscript-session-1", "DIFFERENT LABELLED NATIVE RESPONSE"))
        (call["directory"] / "receipt.json").write_text(json.dumps({"response": (call["directory"] / "response.txt").read_text(), "completed": True}))
        self.fixture.invalid("Actual native worker message differs")

    def test_successful_retained_text_does_not_mask_native_failed_result(self):
        call = self.fixture.calls[2]
        write_events(call["directory"], claude_events("labelled-manuscript-session-2", (call["directory"] / "response.txt").read_text(), failed=True))
        self.fixture.invalid("Native worker did not complete")

    def test_codex_lookalike_events_cannot_prove_native_backend_success(self):
        call = self.fixture.calls[0]
        raw = (call["directory"] / "response.txt").read_text()
        write_events(call["directory"], [{"type": "thread.started", "thread_id": "fake-native-session"},
                    {"type": "item.completed", "item": {"type": "agent_message", "text": raw}}, {"type": "turn.completed"}])
        self.fixture.invalid("Native worker did not complete")

    def replace_with_acp_fixture_process(self, call, backend):
        """Use the shared labelled protocol server, never an installed agent CLI."""
        directory = call["directory"]
        raw = (directory / "response.txt").read_text()
        prompt = (directory / "prompt.txt").read_text()
        selection = {"backend": backend, "model": "fixture-model-a", "effort": None}
        plan = transports.prepare_invocation(selection, prompt, [], False, directory)
        server = acp_fixtures.SERVER.replace('"text":"LABELLED "', '"text":' + json.dumps(raw)).replace('"text":"ARTIFACT"', '"text":""')
        plan["command"] = [sys.executable, "-u", "-c", server] + plan["command"][1:]
        (directory / "transport.json").write_text(json.dumps(plan))
        request = json.loads((directory / "request.json").read_text())
        request.update(backend=backend, search_required=False, images=[], image_sha256={},
                       model_routing=selection, transport_plan_sha256=hashlib.sha256((directory / "transport.json").read_bytes()).hexdigest())
        (directory / "request.json").write_text(json.dumps(request))
        call["start"]["backend"] = backend
        pids = []
        self.assertEqual(transports.execute_invocation(plan, directory, 5, pids.append), raw)
        self.assertEqual(len(pids), 1)
        receipt = transports.inspect_invocation(directory, request)
        self.assertTrue(receipt["completed"], receipt)
        self.assertEqual(receipt["response"], raw)
        return directory

    def test_antigravity_actual_wire_proves_original_parse_effective_and_compile_chain(self):
        directory = self.replace_with_acp_fixture_process(self.fixture.calls[0], "antigravity")
        self.assertTrue((directory / "acp-wire.jsonl").is_file())
        summary, errors = self.fixture.audit()
        self.assertEqual(errors, [])
        self.assertTrue(summary["valid"])
        events = transports.read_events(directory / "events.jsonl")
        next(event for event in events if event.get("method") == "session/update")["params"]["update"]["content"]["text"] = "TAMPERED LABELLED NATIVE RESPONSE"
        write_events(directory, events)
        self.fixture.invalid("Native worker did not complete")

    def test_vibe_actual_wire_proves_original_parse_effective_and_compile_chain(self):
        directory = self.replace_with_acp_fixture_process(self.fixture.calls[1], "mistral-vibe")
        self.assertTrue((directory / "acp-wire.jsonl").is_file())
        summary, errors = self.fixture.audit()
        self.assertEqual(errors, [])
        self.assertTrue(summary["valid"])

    def test_duplicate_native_request_id_cannot_hide_an_extra_fresh_session(self):
        directory = self.replace_with_acp_fixture_process(self.fixture.calls[0], "antigravity")
        path = directory / "acp-wire.jsonl"
        records = transports.read_events(path)
        index = next(i for i, record in enumerate(records) if record["direction"] == "send"
                     and record["message"].get("method") == "session/new")
        records.insert(index + 1, copy.deepcopy(records[index]))
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        self.fixture.invalid("Native worker did not complete")


class NativeExecutionPolicyAuditTests(unittest.TestCase):
    """Schema2 policy evidence binds selected fields to native argv and input."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="labelled-native-policy-audit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        profile = {"schema_version": 2, "name": "labelled native audit fixture",
                   "default": {"backend": "claude-code", "model": "claude-labelled-fixture", "effort": "high"},
                   "roles": {"peer-reviewer": {"effort": "medium"}}}
        def executor(command, prompt, directory):
            request = json.loads((directory / "request.json").read_text())
            events = claude_events(directory.name, '{"labelled_fixture":true}')
            events[0]["effort"] = request["model_routing"]["effort"]
            write_events(directory, events)
            return '{"labelled_fixture":true}'
        self.runtime = Runtime(self.root / "execution", model_profile=profile, executor=executor)
        for role in ("outline", "peer-reviewer"):
            token = role_override.set(role)
            try:
                self.runtime.generate(["LABELLED POLICY INPUT"], {}, "u")
            finally:
                role_override.reset(token)
        self.trace = [json.loads(line) for line in (self.runtime.root / "trace.jsonl").read_text().split("\n") if line]
        profile_path = self.runtime.root / "model_profile.json"
        profile_path.write_text(json.dumps(self.runtime.model_policy.reusable_profile()))
        source_path = self.runtime.root / "model_profile.source.json"
        source_path.write_text(json.dumps(profile))
        self.run = {"model_policy": self.runtime.model_policy.snapshot(),
                    "model_profile_snapshot_sha256": self.sha(profile_path),
                    "model_profile_source": {"path": "labelled-profile.json", "sha256": self.sha(source_path)}}

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def audit(self):
        return audit_model_policy(self.root, self.run, self.trace)

    def invalid(self):
        summary, errors = self.audit()
        self.assertFalse(summary["valid"], summary)
        self.assertTrue(errors)

    def start(self):
        return next(event for event in self.trace if event["event"] == "agent_start")

    def test_valid_v2_policy_matches_native_backend_model_and_effort(self):
        summary, errors = self.audit()
        self.assertEqual(errors, [])
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["attempts_checked"], 2)

    def test_tampered_native_effort_argv_is_rejected(self):
        start = self.start()
        start["command"][start["command"].index("--effort") + 1] = "low"
        self.invalid()

    def test_backend_executable_tamper_is_rejected_even_when_model_and_effort_match(self):
        self.start()["command"][0] = "codex"
        self.invalid()

    def test_request_backend_cannot_disagree_with_selected_runtime(self):
        start = self.start()
        path = self.runtime.root / "invocations" / start["invocation"] / "request.json"
        request = json.loads(path.read_text())
        request["backend"] = "codex"
        path.write_text(json.dumps(request))
        self.invalid()

    def test_flat_native_profile_tamper_is_rejected_even_if_snapshot_hash_is_updated(self):
        path = self.runtime.root / "model_profile.json"
        profile = json.loads(path.read_text())
        profile["roles"]["outline"]["effort"] = "low"
        path.write_text(json.dumps(profile))
        self.run["model_profile_snapshot_sha256"] = self.sha(path)
        self.invalid()

    def test_original_native_profile_tamper_is_rejected_even_if_source_hash_is_updated(self):
        path = self.runtime.root / "model_profile.source.json"
        profile = json.loads(path.read_text())
        profile["default"]["backend"] = "codex"
        path.write_text(json.dumps(profile))
        self.run["model_profile_source"]["sha256"] = self.sha(path)
        self.invalid()


class MultiRuntimeTraceAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = trace_fixtures.TraceAuditTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def native(self, key, *, session=None, failed=False, search=None):
        directory = self.fixture.agent_dirs[key]
        start = next(e for e in self.fixture.trace if e["event"] == "agent_start" and e["invocation"] == key)
        end = next(e for e in self.fixture.trace if e["event"] == "agent_end" and e["invocation"] == key)
        request = json.loads((directory / "request.json").read_text())
        request.update(backend="claude-code", model_routing={"model": "claude-labelled-fixture", "effort": "high"})
        (directory / "request.json").write_text(json.dumps(request))
        start.update(backend="claude-code", command=["claude", "--print", "--output-format", "stream-json", "--model", "claude-labelled-fixture", "--effort", "high"])
        session = session or end["sessions"][0]
        end["sessions"] = [session]
        events = claude_events(session, (directory / "response.txt").read_text(),
                               search=request["search_required"] if search is None else search, failed=failed)
        write_events(directory, events)
        return events

    def test_mixed_native_discovery_and_codex_ensemble_preserve_all_handoffs(self):
        self.native(self.fixture.discovery)
        result = self.fixture.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(result["ensembles"], 1)
        self.assertEqual(len(result["handoffs"]), 4)

    def test_same_provider_session_reuse_is_rejected(self):
        self.native(self.fixture.discovery, session="labelled-reused-native-session")
        self.native(self.fixture.chair, session="labelled-reused-native-session")
        self.fixture.assert_invalid("reused a session")

    def test_equal_session_strings_from_distinct_providers_are_independent(self):
        codex_session = next(e["sessions"][0] for e in self.fixture.trace
                             if e["event"] == "agent_end" and e["invocation"] == self.fixture.chair)
        self.native(self.fixture.discovery, session=codex_session)
        result = self.fixture.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])

    def test_native_search_prose_and_failed_result_cannot_pass_trace_audit(self):
        self.native(self.fixture.discovery, search=False)
        self.fixture.assert_invalid()
        self.native(self.fixture.discovery, failed=True, search=True)
        self.fixture.assert_invalid()

    def test_native_request_backend_and_retained_text_must_match_raw_proof(self):
        self.native(self.fixture.discovery)
        directory = self.fixture.agent_dirs[self.fixture.discovery]
        events = transports.read_events(directory / "events.jsonl")
        events[-1]["result"] = "DIFFERENT LABELLED NATIVE RESPONSE"
        write_events(directory, events)
        self.fixture.assert_invalid()


if __name__ == "__main__":
    unittest.main(verbosity=2)
