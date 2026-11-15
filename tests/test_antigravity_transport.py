"""Antigravity/common ACP protocol tests with a labelled local fixture server.

The fixture subprocess is not a model. No Antigravity inference or provider API
is called. Actual installed CLI capabilities were probed separately without prompts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper-orchestra/vendor"))
import orchestra_acp as acp
import orchestra_antigravity as antigravity

# Native-shaped JSON-RPC messages emitted by a labelled test process only.
SERVER = r'''import json, os, sys, time
mode=os.environ.get("LABELLED_ACP_FIXTURE_MODE", "normal")
sid="labelled-native-fixture-session-"+str(os.getpid())
current={"model":"fixture-model-a","thought_level":"high","mode":"default"}
def emit(x): print(json.dumps(x),flush=True)
def reply(n,result): emit({"jsonrpc":"2.0","id":n,"result":result})
def opts(): return [{"id":k,"type":"select","currentValue":v,"options":[{"value":x,"name":x} for x in (["fixture-model-a","fixture-model-b"] if k=="model" else ["low","high"] if k=="thought_level" else ["default"])]} for k,v in current.items()]
for line in sys.stdin:
 m=json.loads(line);method=m.get("method");n=m.get("id");p=m.get("params",{})
 if method=="initialize": reply(n,{"protocolVersion":1,"agentInfo":{"name":"LABELLED ACP FIXTURE"},"agentCapabilities":{"promptCapabilities":{"image":mode!="no-image"},"sessionCapabilities":{"close":{}}}})
 elif method=="session/new": reply(n,{"sessionId":sid,"configOptions":opts()})
 elif method=="session/set_config_option":
  if mode=="preprompt-config-notifications": emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":{"sessionUpdate":"config_option_update","configOptions":opts()}}})
  if mode!="wrong-config": current[p["configId"]]=p["value"]
  reply(n,{"configOptions":opts()})
 elif method=="session/prompt":
  if mode=="timeout": time.sleep(10)
  if mode=="native-error":
   emit({"jsonrpc":"2.0","id":n,"error":{"code":-32000,"message":"LABELLED PROVIDER ERROR"}});continue
  if mode=="malformed":
   print("LABELLED MALFORMED STDOUT {",flush=True);continue
  if mode in {"multi-message","search-epoch"}:
   first={"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"LABELLED PRE-TOOL NARRATION"}}
   if mode=="multi-message":first["messageId"]="narration-id"
   emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":first}})
  if mode in {"tool","search","failed-search","search-no-permission-name","search-epoch","ag-status-search","ag-status-mismatch"}:
   name="run_command" if mode=="tool" else "search_web"
   tool={"sessionUpdate":"tool_call","toolCallId":"fixture-tool-1","title":"LABELLED NATIVE TOOL", "kind":"execute" if mode=="tool" else "search", "status":"in_progress", "_meta":{"tool_name":name},"rawInput":{"query":"labelled fixture query"}}
   if mode in {"ag-status-search","ag-status-mismatch"}: tool.update({"name":"search_web","args":{"query":"labelled fixture query"}})
   emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":tool}})
   if mode in {"ag-status-search","ag-status-mismatch"}:
    finish={"sessionUpdate":"tool_call_update","toolCallId":"fixture-tool-1","name":"search_web","args":{"query":"different query" if mode=="ag-status-mismatch" else "labelled fixture query"},"rawInput":{"query":"labelled fixture query"},"kind":"search","status":"completed"}
    emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":finish}})
   elif mode!="tool":
    permission_tool={"toolCallId":"fixture-tool-1"} if mode=="search-no-permission-name" else tool
    emit({"jsonrpc":"2.0","id":"permission-fixture","method":"session/request_permission","params":{"sessionId":sid,"toolCall":permission_tool,"options":[{"optionId":"allow-fixture","name":"Allow once","kind":"allow_once"},{"optionId":"deny-fixture","name":"Deny once","kind":"reject_once"}]}})
    permission=json.loads(sys.stdin.readline())
    accepted=permission.get("result",{}).get("outcome",{}).get("optionId")=="allow-fixture"
    update={"sessionUpdate":"tool_call_update","toolCallId":"fixture-tool-1","status":"completed" if accepted and mode!="failed-search" else "failed", "rawOutput":{"query":"labelled fixture query","sources":["https://example.invalid/fixture"]} if accepted and mode!="failed-search" else {"error":"LABELLED SEARCH FAILURE"}}
    emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":update}})
  emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":{"sessionUpdate":"agent_message_chunk","messageId":"final-id" if mode=="multi-message" else None,"content":{"type":"text","text":"LABELLED "}}}})
  emit({"jsonrpc":"2.0","method":"session/update","params":{"sessionId":sid,"update":{"sessionUpdate":"agent_message_chunk","messageId":"final-id" if mode=="multi-message" else None,"content":{"type":"text","text":"ARTIFACT"}}}})
  reply(n,{"stopReason":"max_tokens" if mode=="truncated" else "end_turn"})
 elif method=="session/close": reply(n,{})
'''


class AntigravityTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paper-orchestra-agy-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / "invocation"
        self.directory.mkdir()
        self.prompt = "LABELLED FIXTURE TASK: return the requested artifact."
        self.processes = []

    def prepare(self, *, model="fixture-model-b", effort="low", search=False, images=(), mode="normal"):
        plan = antigravity.prepare({"backend":"antigravity", "model":model, "effort":effort}, self.prompt, images, search, self.directory)
        # Replace only the executable with an explicitly labelled native-shaped fixture.
        plan["command"] = [sys.executable, "-u", "-c", SERVER] + plan["command"][1:]
        plan["env"]["LABELLED_ACP_FIXTURE_MODE"] = mode
        (self.directory / "transport.json").write_text(json.dumps(plan, indent=2))
        (self.directory / "prompt.txt").write_text(self.prompt)
        request = {"backend":"antigravity", "command":plan["command"], "search_required":search,
                   "model_routing":{"backend":"antigravity", "model":model, "effort":effort},
                   "transport_plan_sha256":acp.digest(self.directory / "transport.json"),
                   "images":[str(Path(image).resolve()) for image in images],
                   "image_sha256":{str(Path(image).resolve()):acp.digest(image) for image in images}}
        (self.directory / "request.json").write_text(json.dumps(request))
        return plan, request

    def run_fixture(self, **kwargs):
        plan, request = self.prepare(**kwargs)
        result = antigravity.execute(plan, self.directory, 5, self.processes.append)
        return result, antigravity.inspect(self.directory, request), plan, request

    def mutate_wire(self, mutate):
        file = self.directory / "acp-wire.jsonl"
        records = acp.read_jsonl(file)
        mutate(records)
        file.write_text("".join(json.dumps(record)+"\n" for record in records))
        (self.directory / "events.jsonl").write_text("".join(json.dumps(record["message"])+"\n" for record in records if record["direction"]=="receive"))

    def test_prepare_scopes_tools_and_never_requests_conversation_resume(self):
        plan = antigravity.prepare({"model":None,"effort":None},self.prompt,[],False,self.directory)
        definition = Path(plan["acp"]["agent_file"]).read_text()
        self.assertIn("tools: []", definition)
        self.assertIn("subagent: false", definition)
        self.assertIn("--process-per-session", plan["command"])
        self.assertNotIn("--dangerously-skip-permissions", plan["command"])
        settings=json.loads(plan["command"][plan["command"].index("--settings")+1])
        self.assertIn("command(*)", settings["permissions"]["deny"])
        self.assertIn("read_url(*)", settings["permissions"]["deny"])

    def test_fresh_native_session_and_model_effort_acknowledgments(self):
        result, receipt, plan, request = self.run_fixture()
        self.assertEqual(result,"LABELLED ARTIFACT")
        self.assertTrue(receipt["completed"],receipt)
        self.assertEqual(len(self.processes),1)
        self.assertEqual(receipt["observed_model"],"fixture-model-b")
        self.assertEqual(receipt["observed_effort"],"low")
        self.assertEqual(len(receipt["sessions"]),1)
        outgoing=[x["message"] for x in acp.read_jsonl(self.directory/"acp-wire.jsonl") if x["direction"]=="send"]
        self.assertEqual(sum(m.get("method")=="session/new" for m in outgoing),1)
        self.assertFalse(any(m.get("method") in {"session/load","session/resume"} for m in outgoing))

    def test_inline_images_are_actual_bytes_and_every_image_is_verified(self):
        from PIL import Image
        paths=[]
        for index,color in enumerate(["red","blue"]):
            path=self.root/f"page-{index}.png";Image.new("RGB",(9,9),color).save(path);paths.append(path)
        result,receipt,plan,request=self.run_fixture(images=paths)
        self.assertTrue(receipt["completed"],receipt)
        self.assertEqual(receipt["images_delivered"],request["images"])
        def omit(records):
            prompt=next(row["message"] for row in records if row["direction"]=="send" and row["message"].get("method")=="session/prompt")
            prompt["params"]["prompt"].pop()
        self.mutate_wire(omit)
        receipt=antigravity.inspect(self.directory,request)
        self.assertFalse(receipt["completed"])
        self.assertTrue(any("omitted" in error for error in receipt["errors"]),receipt)

    def test_native_completed_search_and_matching_permission_are_required(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="search")
        self.assertTrue(receipt["completed"],receipt)
        self.assertTrue(receipt["searched"])
        outgoing=[row["message"] for row in acp.read_jsonl(self.directory/"acp-wire.jsonl") if row["direction"]=="send"]
        answer=next(item for item in outgoing if item.get("id")=="permission-fixture")
        self.assertEqual(answer["result"]["outcome"]["optionId"],"allow-fixture")

    def test_permission_identity_can_be_correlated_to_prior_native_tool_start(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="search-no-permission-name")
        self.assertTrue(receipt["completed"],receipt)
        self.assertTrue(receipt["searched"])

    def test_search_words_in_response_do_not_substitute_for_tool_events(self):
        result,receipt,plan,request=self.run_fixture(search=True)
        self.assertFalse(receipt["completed"])
        self.assertFalse(receipt["searched"])
        self.assertTrue(any("no completed native search" in error for error in receipt["errors"]))

    def test_failed_search_does_not_satisfy_search_evidence(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="failed-search")
        self.assertFalse(receipt["completed"])
        self.assertFalse(receipt["searched"])

    def test_disallowed_tool_aborts_the_worker(self):
        plan,request=self.prepare(mode="tool")
        with self.assertRaisesRegex(acp.ACPError,"disallowed tool"):
            antigravity.execute(plan,self.directory,5,self.processes.append)
        receipt=antigravity.inspect(self.directory,request)
        self.assertFalse(receipt["completed"])

    def test_unknown_model_fails_before_prompt_instead_of_substitution(self):
        plan,request=self.prepare(model="unadvertised-model")
        with self.assertRaisesRegex(acp.ACPError,"not advertised"):
            antigravity.execute(plan,self.directory,5,self.processes.append)
        outgoing=[row["message"] for row in acp.read_jsonl(self.directory/"acp-wire.jsonl") if row["direction"]=="send"]
        self.assertFalse(any(item.get("method")=="session/prompt" for item in outgoing))

    def test_model_effort_mismatch_acknowledgment_fails_before_prompt(self):
        plan,request=self.prepare(mode="wrong-config")
        with self.assertRaisesRegex(acp.ACPError,"did not acknowledge"):
            antigravity.execute(plan,self.directory,5,self.processes.append)

    def test_truncated_native_turn_is_never_success(self):
        plan,request=self.prepare(mode="truncated")
        with self.assertRaisesRegex(acp.ACPError,"did not complete"):
            antigravity.execute(plan,self.directory,5,self.processes.append)
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])

    def test_native_provider_error_is_retained_and_not_completed(self):
        plan,request=self.prepare(mode="native-error")
        with self.assertRaisesRegex(acp.ACPError,"LABELLED PROVIDER ERROR"):
            antigravity.execute(plan,self.directory,5,self.processes.append)
        self.assertIn("LABELLED PROVIDER ERROR",(self.directory/"events.jsonl").read_text())
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])

    def test_timeout_kills_only_the_fixture_process_group_and_records_failure(self):
        plan,request=self.prepare(mode="timeout")
        with self.assertRaises(TimeoutError):
            antigravity.execute(plan,self.directory,.15,self.processes.append)
        status=json.loads((self.directory/"acp-exit.json").read_text())
        self.assertFalse(status["completed_turn"])
        self.assertTrue(status["error"])

    def test_inspector_rejects_changed_native_model_receipt(self):
        result,receipt,plan,request=self.run_fixture()
        def change(records):
            for row in records:
                if row["direction"]=="receive":
                    for option in row["message"].get("result",{}).get("configOptions",[]):
                        if option["id"]=="model":option["currentValue"]="wrong-model"
        self.mutate_wire(change)
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])

    def test_inspector_rejects_resumed_session_even_with_end_turn(self):
        result,receipt,plan,request=self.run_fixture()
        def change(records):
            records.insert(0,{"direction":"send","message":{"jsonrpc":"2.0","id":100,"method":"session/load","params":{"sessionId":"old-conversation"}}})
        self.mutate_wire(change)
        receipt=antigravity.inspect(self.directory,request)
        self.assertTrue(any("resumed" in error for error in receipt["errors"]),receipt)

    def test_final_native_message_excludes_separately_identified_narration(self):
        result,receipt,plan,request=self.run_fixture(mode="multi-message")
        self.assertEqual(result,"LABELLED ARTIFACT")
        self.assertTrue(receipt["completed"],receipt)
        self.assertIn("LABELLED PRE-TOOL NARRATION",(self.directory/"events.jsonl").read_text())

    def test_tool_start_delimits_narration_when_native_message_id_is_absent(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="search-epoch")
        self.assertEqual(result,"LABELLED ARTIFACT")
        self.assertTrue(receipt["completed"],receipt)
        self.assertTrue(receipt["searched"])

    def test_malformed_native_stdout_is_retained_before_parse_failure(self):
        plan,request=self.prepare(mode="malformed")
        with self.assertRaisesRegex(acp.ACPError,"malformed JSON"):
            antigravity.execute(plan,self.directory,5,self.processes.append)
        self.assertIn("LABELLED MALFORMED STDOUT {",(self.directory/"events.jsonl").read_text())
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])

    def test_orphan_completed_tool_update_is_not_native_search_proof(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="search")
        def orphan(records):
            for row in records:
                update=row["message"].get("params",{}).get("update",{})
                if update.get("sessionUpdate")=="tool_call":update["sessionUpdate"]="tool_call_update"
        self.mutate_wire(orphan)
        receipt=antigravity.inspect(self.directory,request)
        self.assertFalse(receipt["completed"])
        self.assertFalse(receipt["searched"])
        self.assertTrue(any("no matching call start" in error for error in receipt["errors"]),receipt)

    def test_native_search_must_belong_to_the_current_prompt_turn(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="search")
        def move(records):
            search=[row for row in records if row["direction"]=="receive" and row["message"].get("params",{}).get("update",{}).get("sessionUpdate") in {"tool_call","tool_call_update"}]
            records[:]=[row for row in records if row not in search]
            index=next(index for index,row in enumerate(records) if row["direction"]=="send" and row["message"].get("method")=="session/prompt")
            records[index:index]=search
        self.mutate_wire(move)
        receipt=antigravity.inspect(self.directory,request)
        self.assertFalse(receipt["completed"])
        self.assertFalse(receipt["searched"])
        self.assertTrue(any("outside its prompt turn" in error for error in receipt["errors"]),receipt)

    def test_native_midturn_model_change_is_not_silently_accepted(self):
        result,receipt,plan,request=self.run_fixture()
        def change(records):
            index=next(index for index,row in enumerate(records) if row["direction"]=="send" and row["message"].get("method")=="session/prompt")+1
            records.insert(index,{"direction":"receive","message":{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":receipt["sessions"][0],"update":{"sessionUpdate":"config_option_update","configOptions":[{"id":"model","currentValue":"different-model"}]}}}})
        self.mutate_wire(change)
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])

    def test_observed_ag_preprompt_old_effort_notification_does_not_override_final_ack(self):
        result,receipt,plan,request=self.run_fixture(mode="preprompt-config-notifications")
        self.assertTrue(receipt["completed"],receipt)
        self.assertEqual(receipt["observed_effort"],"low")

    def test_observed_ag_search_name_query_and_completed_status_prove_native_execution(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="ag-status-search")
        self.assertTrue(receipt["completed"],receipt)
        self.assertTrue(receipt["searched"])
        self.assertTrue(any(row["message"].get("params",{}).get("update",{}).get("status")=="completed"
                            and "rawOutput" not in row["message"].get("params",{}).get("update",{})
                            for row in acp.read_jsonl(self.directory/"acp-wire.jsonl")))

    def test_payloadless_ag_completion_with_changed_query_is_not_search_proof(self):
        result,receipt,plan,request=self.run_fixture(search=True,mode="ag-status-mismatch")
        self.assertFalse(receipt["completed"])
        self.assertFalse(receipt["searched"])

    def test_unexpected_effort_after_final_ack_before_prompt_is_still_rejected(self):
        result,receipt,plan,request=self.run_fixture()
        def change(records):
            index=next(index for index,row in enumerate(records) if row["direction"]=="send" and row["message"].get("method")=="session/prompt")
            records.insert(index,{"direction":"receive","message":{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":receipt["sessions"][0],"update":{"sessionUpdate":"config_option_update","configOptions":[{"id":"thought_level","currentValue":"high"}]}}}})
        self.mutate_wire(change)
        receipt=antigravity.inspect(self.directory,request)
        self.assertFalse(receipt["completed"])
        self.assertEqual(receipt["observed_effort"],"high")

    def test_changed_scoped_agent_definition_is_rejected(self):
        result,receipt,plan,request=self.run_fixture()
        file=Path(plan["acp"]["agent_file"]);file.write_text(file.read_text().replace("tools: []","tools: [run_command]"))
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])

    def test_plan_must_be_hash_anchored_to_request(self):
        result,receipt,plan,request=self.run_fixture()
        request["transport_plan_sha256"]="0"*64
        self.assertFalse(antigravity.inspect(self.directory,request)["completed"])


if __name__=="__main__":unittest.main(verbosity=2)
