"""Adversarial audit tests using labelled trace fixtures, never actual model runs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "paper_orchestra_trace_audit", ROOT / "paper-orchestra/scripts/summarize_trace.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TraceAuditTests(unittest.TestCase):
    """Fixtures model the recording protocol, not scientific output or agent execution."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.execution = self.root / "execution"
        self.execution.mkdir()
        self.trace = []
        self.counter = 0
        self.hashes = {}
        self.agent_dirs = {}
        self.write_artifact("outline.json", '{"fixture":"enriched outline"}')
        self.write_artifact("literature_agent_output/outline_v1.json", '{"fixture":"enriched outline"}')
        self.write_artifact("latex_writeup/template.tex", "fixture intro and related work")
        self.write_artifact("literature_agent_output/updated_template.tex", "fixture intro and related work")
        self.write_artifact("latex_writeup/references.bib", "fixture bibliography")
        self.write_artifact("literature_agent_output/references.bib", "fixture bibliography")
        self.write_artifact("literature_agent_output/citation_map.json", '{"fixture":"citation map"}')
        self.write_artifact("latex_writeup/raw_draft_paper.tex", "fixture full draft")
        self.write_artifact("content_refinement_workdir/raw_draft_paper.tex", "fixture full draft")
        self.write_artifact("content_refinement_workdir/final_refined_paper.tex", "fixture final tex")
        self.write_artifact("content_refinement_workdir/final_refined_paper.pdf", "%PDF-1.4\n% TRACE AUDITOR FIXTURE ONLY\n%%EOF\n")
        self.write_artifact("final_paper.pdf", "%PDF-1.4\n% TRACE AUDITOR FIXTURE ONLY\n%%EOF\n")
        self.append("run_start", status="running", plotting=False)
        self.add_agent("runtime-probe")
        self.append("stage_start", stage="OutlineAgent", span="outline-stage", inputs=dict(self.hashes))
        self.add_agent("outline")
        self.append("stage_end", stage="OutlineAgent", span="outline-stage", outputs=dict(self.hashes))
        self.append("stage_start", stage="HybridLiteratureAgent", span="lit-stage", inputs=dict(self.hashes))
        self.discovery = self.add_agent("literature-discovery", search=True)
        self.add_agent("literature-synthesis")
        self.append("stage_end", stage="HybridLiteratureAgent", span="lit-stage", outputs=dict(self.hashes))
        self.append("stage_start", stage="SectionWritingAgent", span="section-stage", inputs=dict(self.hashes))
        self.add_agent("section-writer")
        self.append("stage_end", stage="SectionWritingAgent", span="section-stage", outputs=dict(self.hashes))
        self.append("stage_start", stage="ContentRefinementAgent", span="refine-stage", inputs=dict(self.hashes))
        self.append("compile_start", tex=str(self.root / "content_refinement_workdir/initial_draft.tex"),
                    pdf=str(self.root / "content_refinement_workdir/initial_draft.pdf"))
        self.append("compile_end", pdf=str(self.root / "content_refinement_workdir/initial_draft.pdf"),
                    exists=True, sha256=self.hashes["final_paper.pdf"])
        self.reviewers = [self.add_agent("peer-reviewer") for _ in range(3)]
        self.chair = self.add_agent("area-chair")
        # An editor may stop on empty LaTeX; formatting remains an independent call.
        self.add_agent("content-or-format-editor")
        self.add_agent("format-reviewer")
        self.append("stage_end", stage="ContentRefinementAgent", span="refine-stage", outputs=dict(self.hashes))
        self.append("run_end", status="completed")
        self.run = {"status": "completed", "plotting": False,
                    "upstream_commit": "ca1b3fa01c2970fc7cda32d16245db38d57b3f56",
                    "artifacts": dict(self.hashes)}
        self.save()

    def append(self, event, **fields):
        self.trace.append({"seq": len(self.trace) + 1, "time": float(len(self.trace)),
                           "event": event, **fields})

    def write_artifact(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.hashes[relative] = digest(path)

    def add_agent(self, role, *, search=False):
        self.counter += 1
        key = f"fixture-invocation-{self.counter:03}"
        call = f"fixture-call-{self.counter:03}"
        session = f"fixture-session-{self.counter:03}"
        directory = self.execution / "invocations" / key
        directory.mkdir(parents=True)
        (directory / "prompt.txt").write_text(f"TRACE FIXTURE ONLY: independent {role}")
        (directory / "response.txt").write_text('{"fixture":true}')
        raw_events = [{"type": "thread.started", "thread_id": session}]
        if search:
            raw_events.append({"type": "item.completed", "item": {"type": "web_search", "status": "completed", "action": {"type": "search", "query": "fixture query"}}})
        raw_events.extend([{"type": "item.completed", "item": {"type": "agent_message", "text": "fixture response"}},
                           {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}])
        self.write_raw(key, raw_events, directory=directory)
        request = {"invocation": key, "call": call, "role": role, "search_required": search,
                   "prompt_sha256": digest(directory / "prompt.txt"), "media": [], "images": [],
                   "requested_model": "fixture-upstream", "effective_model": "fixture-codex"}
        (directory / "request.json").write_text(json.dumps(request))
        parsed = self.execution / "parsed" / f"{call}.json"
        parsed.parent.mkdir(exist_ok=True)
        parsed.write_text('{"fixture":true}')
        self.append("llm_call_start", call=call, role=role)
        self.append("agent_start", **request, command=["codex", "exec", "--ephemeral", "--json", "-"])
        self.append("process_started", invocation=key, pid=30000 + self.counter)
        self.append("agent_end", invocation=key, role=role, sessions=[session], searched=search,
                    response_sha256=digest(directory / "response.txt"))
        self.append("llm_call_end", call=call, parsed_path=str(parsed), sha256=digest(parsed))
        self.agent_dirs[key] = directory
        return key

    def raw(self, key):
        return [json.loads(line) for line in (self.agent_dirs[key] / "events.jsonl").read_text().splitlines()]

    def write_raw(self, key, events, directory=None):
        directory = directory or self.agent_dirs[key]
        (directory / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))

    def save(self):
        for index, event in enumerate(self.trace):
            event["seq"] = index + 1
            event["time"] = float(index)
        (self.root / "run.json").write_text(json.dumps(self.run))
        (self.execution / "trace.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.trace))

    def insert_failed_ensemble(self, completed_count=1, failed_role="peer-reviewer", *, actual_error=True):
        """Insert a labelled partial ensemble before the ordinary complete one.

        A concrete nonretryable 400 agent failure ends its upstream model call;
        _get_peer_review then supplies Overall=0 without saving an aggregate.
        """
        original = list(self.trace)
        self.trace = []
        for _ in range(completed_count):
            self.add_agent("peer-reviewer")
        failed = self.add_agent(failed_role)
        request = next(e for e in self.trace if e["event"] == "agent_start" and e["invocation"] == failed)
        call = request["call"]
        self.trace = [e for e in self.trace if not (
            (e["event"] == "agent_end" and e["invocation"] == failed)
            or (e["event"] == "llm_call_end" and e["call"] == call))]
        events = self.raw(failed)
        events = [e for e in events if e.get("type") != "turn.completed"]
        events.append({"type": "turn.failed", "error": {"message": "400 bad request"}})
        self.write_raw(failed, events)
        if actual_error:
            self.append("agent_error", invocation=failed, error="400 bad request")
        self.append("llm_call_error", call=call, error="400 bad request")
        added = self.trace
        first_call = next(e["call"] for e in original if e["event"] == "agent_start" and e["invocation"] == self.reviewers[0])
        where = next(i for i, e in enumerate(original) if e["event"] == "llm_call_start" and e["call"] == first_call)
        self.trace = original[:where] + added + original[where:]
        return failed, call

    def audit(self):
        self.save()
        return AUDIT.summarize(self.root)

    def assert_invalid(self, contains=None):
        result = self.audit()
        self.assertFalse(result["evidence_valid"], result)
        if contains:
            self.assertTrue(any(contains in error for error in result["errors"]), result["errors"])

    def test_valid_labelled_fixture_contains_independent_sessions_and_handoffs(self):
        result = self.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(result["ensembles"], 1)
        self.assertEqual(result["unique_sessions"], self.counter)
        self.assertEqual(len(result["handoffs"]), 4)

    def test_whole_paper_retry_uses_retained_refinement_review_group(self):
        """Earlier valid ensembles survive only in trace after workdir reset."""
        original = list(self.trace)
        self.trace = []
        self.append("stage_start", stage="ContentRefinementAgent", span="earlier-refinement", inputs=dict(self.hashes))
        earlier = [self.add_agent("peer-reviewer") for _ in range(3)]
        self.add_agent("area-chair")
        self.append("stage_error", stage="ContentRefinementAgent", span="earlier-refinement", error="fixture paper retry")
        previous = self.trace
        where = next(i for i, event in enumerate(original)
                     if event["event"] == "stage_start" and event["stage"] == "ContentRefinementAgent")
        self.trace = original[:where] + previous + original[where:]
        for keys, score in [(earlier, 8), (self.reviewers, 3)]:
            for key in keys:
                start = next(event for event in self.trace if event["event"] == "agent_start" and event["invocation"] == key)
                parsed = self.execution / "parsed" / f"{start['call']}.json"
                parsed.write_text(json.dumps({"Overall":score}))
                end = next(event for event in self.trace if event["event"] == "llm_call_end" and event["call"] == start["call"])
                end["sha256"] = digest(parsed)
        saved = "content_refinement_workdir/peer_reviews/review_v0.json"
        self.write_artifact(saved, json.dumps({"Overall":3}))
        self.run["artifacts"] = dict(self.hashes)
        result = self.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(result["ensembles"], 2)
        self.assertEqual(result["aggregate_score_checks"][0]["scores"],
                         [{"axis":"Overall", "expected":3, "actual":3, "ok":True}])
        self.write_artifact(saved, json.dumps({"Overall":8}))
        self.run["artifacts"] = dict(self.hashes)
        self.assert_invalid("rounded mean")

    def test_agent_prose_cannot_substitute_for_search_tool(self):
        events = [e for e in self.raw(self.discovery) if e.get("item", {}).get("type") != "web_search"]
        events.insert(1, {"type": "item.completed", "item": {"type": "agent_message", "text": "I used web_search"}})
        self.write_raw(self.discovery, events)
        self.assert_invalid("web_search")

    def test_failed_connected_tool_is_not_search_evidence(self):
        events = [e for e in self.raw(self.discovery) if e.get("item", {}).get("type") != "web_search"]
        events.insert(1, {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "codex_apps",
                      "tool": "search_service.web_run", "status": "completed", "error": {"message": "failed"}}})
        self.write_raw(self.discovery, events)
        self.assert_invalid("web_search")

    def test_native_search_error_is_not_successful_search_evidence(self):
        events = self.raw(self.discovery)
        item = next(e["item"] for e in events if e.get("item", {}).get("type") == "web_search")
        item["error"] = {"message": "native search failed"}
        self.write_raw(self.discovery, events)
        self.assert_invalid("web_search")

    def test_connected_search_tool_requires_error_free_result(self):
        events = [e for e in self.raw(self.discovery) if e.get("item", {}).get("type") != "web_search"]
        events.insert(1, {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "codex_apps",
                      "tool": "search_service.web_run", "status": "completed", "error": None,
                      "result": {"isError": True}}})
        self.write_raw(self.discovery, events)
        self.assert_invalid("web_search")

    def test_successful_connected_search_is_accepted(self):
        events = [e for e in self.raw(self.discovery) if e.get("item", {}).get("type") != "web_search"]
        events.insert(1, {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "codex_apps",
                      "tool": "search_service.web_run", "status": "completed", "error": None,
                      "result": {"isError": False}}})
        self.write_raw(self.discovery, events)
        self.assertTrue(self.audit()["evidence_valid"])

    def test_malformed_extra_event_is_warned_and_never_needed_as_proof(self):
        path = self.agent_dirs[self.discovery] / "events.jsonl"
        path.write_text(path.read_text() + '{"type":"item.completed","item":\n')
        before = path.read_bytes()
        result = self.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["warnings"][0]["invocation"], self.discovery)
        self.assertIn("Malformed", result["warnings"][0]["issue"])
        self.assertEqual(len(result["warnings"][0]["line_sha256"]), 64)
        self.assertEqual(path.read_bytes(), before)

    def test_malformed_sole_search_record_cannot_substitute_for_proof(self):
        events = [e for e in self.raw(self.discovery) if e.get("item", {}).get("type") != "web_search"]
        self.write_raw(self.discovery, events)
        path = self.agent_dirs[self.discovery] / "events.jsonl"
        path.write_text(path.read_text() + '{"type":"item.completed","item":{"type":"web_search"\n')
        result = self.audit()
        self.assertFalse(result["evidence_valid"])
        self.assertTrue(any("web_search" in error for error in result["errors"]))
        self.assertEqual(len(result["warnings"]), 1)

    def test_literal_unicode_next_line_inside_json_is_not_a_jsonl_separator(self):
        events = [e for e in self.raw(self.discovery) if e.get("item", {}).get("type") != "web_search"]
        events.insert(1, {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "codex_apps",
                      "tool": "search_service.web_run", "status": "completed", "error": None,
                      "result": {"isError": False, "text": "Search text with literal\u0085Unicode NEL"}}})
        path = self.agent_dirs[self.discovery] / "events.jsonl"
        path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
        self.assertIn("\u0085", path.read_text())
        result = self.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(result["warnings"], [])

    def test_changed_prompt_hash_is_rejected(self):
        (self.agent_dirs[self.discovery] / "prompt.txt").write_text("tampered prompt")
        self.assert_invalid("hash mismatch")

    def test_changed_response_hash_is_rejected(self):
        (self.agent_dirs[self.chair] / "response.txt").write_text("tampered response")
        self.assert_invalid("hash mismatch")

    def test_changed_parsed_model_output_is_rejected(self):
        call = next(e["call"] for e in self.trace if e["event"] == "agent_start" and e["invocation"] == self.chair)
        (self.execution / "parsed" / f"{call}.json").write_text('{"tampered":true}')
        self.assert_invalid("hash mismatch")

    def test_agent_attempt_without_terminal_outcome_is_rejected(self):
        self.trace = [e for e in self.trace if not (e["event"] == "agent_end" and e["invocation"] == self.discovery)]
        self.assert_invalid("terminal outcome")

    def test_reused_session_is_rejected_even_with_consistent_end_event(self):
        first = self.raw(self.reviewers[0])[0]["thread_id"]
        events = self.raw(self.reviewers[1])
        events[0]["thread_id"] = first
        self.write_raw(self.reviewers[1], events)
        next(e for e in self.trace if e["event"] == "agent_end" and e["invocation"] == self.reviewers[1])["sessions"] = [first]
        self.assert_invalid("reused")

    def test_wrong_reviewer_sequence_is_rejected(self):
        chair_call = next(e["call"] for e in self.trace if e["event"] == "agent_start" and e["invocation"] == self.chair)
        event = next(e for e in self.trace if e["event"] == "llm_call_end" and e["call"] == chair_call)
        self.trace.remove(event)
        first_review = next(i for i, e in enumerate(self.trace) if e["event"] == "llm_call_end" and e["call"].endswith("006"))
        self.trace.insert(first_review, event)
        self.assert_invalid("reviewer")

    def test_overlapping_reviewer_calls_violate_upstream_sequential_ensemble(self):
        second_call = next(e["call"] for e in self.trace if e["event"] == "agent_start" and e["invocation"] == self.reviewers[1])
        second_start = next(e for e in self.trace if e["event"] == "llm_call_start" and e["call"] == second_call)
        self.trace.remove(second_start)
        first_end = next(i for i, e in enumerate(self.trace) if e["event"] == "agent_end" and e["invocation"] == self.reviewers[0])
        self.trace.insert(first_end, second_start)
        self.assert_invalid()

    def test_known_partial_failed_peer_ensemble_can_recover_with_complete_ensemble(self):
        self.insert_failed_ensemble(completed_count=1)
        result = self.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(result["ensembles"], 1)

    def test_known_failed_chair_discards_three_partial_reviews_before_recovery(self):
        self.insert_failed_ensemble(completed_count=3, failed_role="area-chair")
        result = self.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertEqual(result["ensembles"], 1)

    def test_call_error_without_verified_failed_attempt_cannot_reset_ensemble(self):
        self.insert_failed_ensemble(completed_count=1, actual_error=False)
        self.assert_invalid()

    def test_orphaned_incomplete_ensemble_without_call_error_is_rejected(self):
        _, failed_call = self.insert_failed_ensemble(completed_count=1)
        self.trace = [e for e in self.trace if not (e["event"] == "llm_call_error" and e["call"] == failed_call)]
        self.assert_invalid()

    def test_section_handoff_with_different_template_hash_is_rejected(self):
        event = next(e for e in self.trace if e["event"] == "stage_start" and e["stage"] == "SectionWritingAgent")
        event["inputs"]["latex_writeup/template.tex"] = "different hash"
        self.assert_invalid("handoff")

    def test_missing_refinement_handoff_cannot_pass_a_completed_run(self):
        self.trace = [e for e in self.trace if not (e["event"] == "stage_start" and e.get("stage") == "ContentRefinementAgent")]
        self.assert_invalid()

    def test_orphaned_reviewer_logs_cannot_substitute_for_agent_processes(self):
        # LLM call logs remain present but their actual process evidence is absent.
        self.trace = [e for e in self.trace if e["event"] not in {"agent_start", "agent_end", "process_started"}]
        self.assert_invalid()

    def test_failed_turn_cannot_be_hidden_by_a_later_completion(self):
        events = self.raw(self.chair)
        events.insert(-1, {"type": "turn.failed", "error": {"message": "failed"}})
        self.write_raw(self.chair, events)
        self.assert_invalid()

    def test_changed_final_pdf_is_rejected_against_manifest(self):
        (self.root / "final_paper.pdf").write_bytes(b"unrelated final artifact")
        self.assert_invalid()


if __name__ == "__main__":
    unittest.main(verbosity=2)
