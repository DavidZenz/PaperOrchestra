"""Persist deterministic upstream-controller traces with explicitly fake effects.

These are branch-coverage evidence, not real agent or scientific results.
Run from the repository root with its dependency environment.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_upstream_conformance import (
    RefinementControllerTests, ReviewerEnsembleTests, PipelineHandoffTests,
    review, paper_writer, paper_writer_with_plotting,
)
from orchestra_runtime import Runtime, configure
from utils.gemini_utils import call_gemini_with_contents


def controlled_refinement(name, reviews, **kwargs):
    case = RefinementControllerTests()
    case.setUp()
    try:
        result = case.run_controller(reviews, **kwargs)
        return {"scenario":name, "input_reviews":reviews,
                "compile_order":result["compilations"],
                "generation_calls":result["generation"].call_count,
                "peer_review_calls":result["peer"].call_count,
                "format_review_calls":result["format"].call_count,
                "decisions":result["agent"].worklogs,
                "format_decisions":result["agent"].format_worklogs,
                "selected_tex_fixture":result["final_tex"],
                "selected_pdf_fixture_bytes":result["final_pdf"].decode(),
                "controller_stdout":case.output.getvalue()}
    finally:
        case.doCleanups()


def pipeline(name, plotting=False, failures=0):
    case = PipelineHandoffTests()
    case.setUp()
    try:
        base, template = case.setup_pipeline()
        fakes, events, state = case.fakes(base, parallel=plotting, outline_failures=failures)
        module = paper_writer_with_plotting if plotting else paper_writer
        if not plotting:
            fakes.pop("PlottingAgent")
        with patch.multiple(module, **fakes):
            success = module.write_single_paper(str(base), str(template))
        return {"scenario":name, "success":success, "events":events,
                "outline_attempts":state["outline_calls"],
                "handoff_assertions":"Actual controller copied artifacts; fake section/refinement workers assert every expected input and branch join.",
                "controller_stdout":case.output.getvalue()}
    finally:
        case.doCleanups()


def main():
    results = {"evidence_type":"controlled fixtures executing actual pinned upstream controller; all model/tool/PDF effects mocked",
               "upstream_commit":"ca1b3fa01c2970fc7cda32d16245db38d57b3f56"}
    results["refinement"] = [
        controlled_refinement("increase_then_drop_revert", [review(5),review(6),review(5)]),
        controlled_refinement("tie_degradation_revert", [review(5),review(5,Quality=1)]),
        controlled_refinement("tie_balanced_accept", [review(5),review(5,Quality=1,Clarity=3),review(4)]),
        controlled_refinement("neutral_cap_three", [review(5)]*4),
        controlled_refinement("compile_failure_consumes_round", [review(5),review(6)], fail_compile={"refined_paper_v1","refined_paper_v3"}),
        controlled_refinement("empty_output_stops", [review(5)], responses=[{"parsed_response":'{"json":{},"latex":null}'}]),
        controlled_refinement("generation_exception_stops", [review(5)], response_error=RuntimeError("fixture provider error")),
        controlled_refinement("format_accept_compile_only", [review(5)], max_reflections=0,
                              formatting={"other_issues":["fixture spacing issue"]},
                              responses=[{"raw_response":"formatted tex fixture"}]),
        controlled_refinement("format_compile_failure_revert", [review(5)], max_reflections=0,
                              formatting={"other_issues":["fixture spacing issue"]},
                              responses=[{"raw_response":"formatted tex fixture"}], fail_compile={"formatted_candidate_v1"}),
    ]
    results["pipeline"] = [pipeline("parallel_branch_join", plotting=True),
                           pipeline("paper_retry_third_success", failures=2),
                           pipeline("paper_retry_exhaustion", failures=99)]
    case = ReviewerEnsembleTests()
    case.setUp()
    try:
        inputs = [review(4),review(6),review(8)]
        output, calls = case.run_ensemble(inputs, review(10,Decision="Reject",Summary="chair fixture"))
        results["ensemble"] = {"individual_reviews":inputs,"chair_input_overall":10,
                               "final_aggregate":output,"call_count":calls.call_count,
                               "call_sequence":["peer-reviewer"]*3+["area-chair"],
                               "controller_stdout":case.output.getvalue()}
    finally:
        case.doCleanups()
    execution = ROOT / "validation" / "controlled-runtime"
    if execution.exists():
        raise SystemExit("controlled-runtime exists; preserve it and choose a fresh validation directory")
    outputs = iter(["invalid JSON fixture","second invalid fixture",'{"recovered":true}'])
    configure(Runtime(execution, executor=lambda *args:next(outputs)))
    stdout = io.StringIO()
    with redirect_stdout(stdout), patch("utils.gemini_utils.time.sleep") as sleep:
        result = call_gemini_with_contents(["retry fixture, no real model"], "fixture-model")
    results["transport_retry"] = {"result":result, "sleep_calls":[c.args[0] for c in sleep.call_args_list],
                                  "trace":"controlled-runtime/trace.jsonl", "controller_stdout":stdout.getvalue()}
    (ROOT / "validation" / "controlled-traces.json").write_text(json.dumps(results,indent=2))
    print("Persisted controlled traces for aggregation, branch joins, retries, acceptance, reversion and stopping.")


if __name__ == "__main__":
    main()
