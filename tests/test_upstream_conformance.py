"""Exercise the vendored authors' controllers, replacing only external effects.

These are behavioral tests against upstream code retained by the port. They do
not reimplement acceptance, aggregation, retry, or scheduling decisions.
"""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "paper-orchestra" / "vendor"
sys.path.insert(0, str(VENDOR))

from autoraters import agent_review as review_module
from methods.agents import content_refinement_agent as refinement_module
from methods.agents import literature_review_agent as literature_module
from methods.agents import section_writing_agent as section_module
from methods.agents import plotting_agent as plotting_module
from methods import paper_writer, paper_writer_with_plotting


AXES = ("Originality", "Quality", "Clarity", "Significance", "Soundness",
        "Presentation", "Contribution")


def review(overall=5, confidence=3, **scores):
    result = {axis: 2 for axis in AXES}
    result.update(Overall=overall, Confidence=confidence, Summary="review")
    result.update(scores)
    return result


class QuietTest(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.quiet = ExitStack()
        self.quiet.enter_context(redirect_stdout(self.output))
        self.quiet.enter_context(redirect_stderr(self.output))
        self.addCleanup(self.quiet.close)


class ReviewerEnsembleTests(QuietTest):
    def run_ensemble(self, reviews, meta):
        responses = [{"parsed_response": value} for value in [*reviews, meta]]
        with patch.object(review_module, "call_gemini_with_text_prompt",
                          side_effect=responses) as call:
            result = review_module.perform_review_agentreview("paper text", "test-model")
        return result, call

    def test_three_independent_reviews_then_chair_and_numeric_override(self):
        individuals = [review(4), review(6), review(8)]
        chair = review(10, Decision="Reject", Summary="chair combines all views")
        result, call = self.run_ensemble(individuals, chair)
        self.assertEqual(call.call_count, 4)
        self.assertEqual(result["Overall"], 6)
        self.assertEqual(result["Decision"], "Reject")
        self.assertEqual(result["Summary"], "chair combines all views")
        # All independent reviewers see the original paper and same persona,
        # never another review. The fourth call alone receives all three.
        for invocation in call.call_args_list[:3]:
            self.assertIn("paper text", invocation.kwargs["prompt"])
            self.assertEqual(invocation.kwargs["generation_configs"]["temperature"], .75)
        self.assertEqual(len({c.kwargs["prompt"] for c in call.call_args_list[:3]}), 1)
        self.assertIn("Review 3/3:", call.call_args_list[3].kwargs["prompt"])
        self.assertIn("area chair", call.call_args_list[3].kwargs["generation_configs"]["system_instruction"])

    def test_int_conversion_bounds_invalid_values_and_bankers_rounding(self):
        # Conversion happens before range validation: 3.9 -> 3, 4.9 -> 4.
        individuals = [review(4, Originality=3.9, Clarity=0, Quality="bad"),
                       review(5, Originality=4.9, Clarity=9, Quality=None),
                       review("invalid", Originality=None, Clarity=-1, Quality=2)]
        chair = review(9, Clarity=4)
        result, _ = self.run_ensemble(individuals, chair)
        self.assertEqual(result["Overall"], 4)  # round(4.5) == 4
        self.assertEqual(result["Originality"], 4)  # round(3.5) == 4
        self.assertEqual(result["Quality"], 2)
        self.assertEqual(result["Clarity"], 4)  # No valid values: retain chair.

    def test_none_meta_review_falls_back_to_first_and_still_aggregates(self):
        individuals = [review(4, Summary="first"), review(6), review(8)]
        result, _ = self.run_ensemble(individuals, None)
        self.assertEqual(result["Summary"], "first")
        self.assertEqual(result["Overall"], 6)

    def test_single_reviewer_does_not_call_chair(self):
        with patch.object(review_module, "call_gemini_with_text_prompt",
                          return_value={"parsed_response": review(7)}) as call:
            result = review_module.perform_review_agentreview("text", "model", num_review_ensemble=1)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["Overall"], 7)


class RefinementControllerTests(QuietTest):
    def run_controller(self, reviews, *, fail_compile=(), responses=None,
                       max_reflections=3, formatting=None, response_error=None):
        tmp = self.quiet.enter_context(tempfile.TemporaryDirectory())
        root = Path(tmp)
        for name, text in [("experimental_log.md", "RAW_DATA_SENTINEL"),
                           ("citation_map.json", '{"reference": "CITATION_SENTINEL"}'),
                           ("guidelines.md", "GUIDELINE_SENTINEL"),
                           ("draft.tex", "baseline tex")]:
            (root / name).write_text(text)
        agent = refinement_module.ContentRefinementAgent(
            str(root / "experimental_log.md"), str(root / "citation_map.json"),
            str(root / "guidelines.md"), work_dir=str(root),
            max_reflections=max_reflections)
        snapshots = []
        compilations = []

        def compile_pdf(cwd, pdf_path, basename):
            compilations.append(basename)
            if basename not in fail_compile:
                # Payload identifies the source selected by the controller.
                Path(pdf_path).write_bytes((Path(cwd) / (basename + ".tex")).read_bytes())

        def screenshots(pdf, out):
            snapshots.append((pdf, out))
            return []

        if responses is None:
            responses = [{"parsed_response": json.dumps({"json": {"plan": i}, "latex": f"candidate tex {i}"})}
                         for i in range(1, max_reflections + 1)]
        generation = Mock(side_effect=response_error if response_error else responses)
        peer = Mock(side_effect=[(r, float(r.get("Overall", 0))) for r in reviews])
        fmt = Mock(return_value=formatting or {"figure_and_tables": {}, "other_issues": []})
        with patch.object(refinement_module, "compile_latex", side_effect=compile_pdf), \
             patch.object(refinement_module, "pdf_to_grid_images", side_effect=screenshots), \
             patch.object(refinement_module, "call_gemini_with_contents", generation), \
             patch.object(agent, "_get_peer_review", peer), \
             patch.object(agent, "_get_formatting_review", fmt):
            output = agent.run(str(root / "draft.tex"))
        return {"agent": agent, "generation": generation, "peer": peer,
                "format": fmt, "compilations": compilations,
                "final_pdf": Path(output).read_bytes(),
                "final_tex": (root / "final_refined_paper.tex").read_text(),
                "snapshots": snapshots}

    def test_increase_accepts_then_lower_score_reverts_to_accepted_version_and_stops(self):
        result = self.run_controller([review(5), review(6), review(5)])
        self.assertEqual(result["final_tex"], "candidate tex 1")
        self.assertEqual(result["final_pdf"], b"candidate tex 1")
        self.assertEqual(result["generation"].call_count, 2)
        self.assertEqual(result["peer"].call_count, 3)
        logs = result["agent"].worklogs
        self.assertEqual(logs["v1"]["outcome"], "ACCEPTED_SCORE_INCREASE")
        self.assertEqual(logs["v2"]["outcome"], "REJECTED_SCORE_DECREASE")
        second = result["generation"].call_args_list[1].kwargs["contents"][1].text
        self.assertIn("candidate tex 1", second)
        self.assertIn("ACCEPTED_SCORE_INCREASE", second)
        for truth in ("RAW_DATA_SENTINEL", "CITATION_SENTINEL", "GUIDELINE_SENTINEL"):
            self.assertIn(truth, second)

    def test_initial_lower_score_rejects_and_retains_baseline_tex_and_pdf(self):
        result = self.run_controller([review(5), review(4)])
        self.assertEqual(result["final_tex"], "baseline tex")
        self.assertEqual(result["final_pdf"], b"baseline tex")
        self.assertEqual(result["generation"].call_count, 1)

    def test_equal_overall_internal_degradation_reverts_and_stops(self):
        result = self.run_controller([review(5), review(5, Quality=1)])
        self.assertEqual(result["final_tex"], "baseline tex")
        self.assertEqual(result["generation"].call_count, 1)
        log = result["agent"].worklogs["v1"]
        self.assertEqual(log["outcome"], "REJECTED_DEGRADATION")
        self.assertEqual(log["total_drop"], 1)
        self.assertEqual(log["total_gain"], 0)

    def test_equal_overall_balanced_changes_are_accepted_and_continue(self):
        result = self.run_controller([review(5), review(5, Quality=1, Clarity=3), review(4)])
        self.assertEqual(result["final_tex"], "candidate tex 1")
        self.assertEqual(result["generation"].call_count, 2)
        log = result["agent"].worklogs["v1"]
        self.assertEqual(log["outcome"], "ACCEPTED_NEUTRAL_IMPROVEMENT")
        self.assertEqual(log["total_drop"], log["total_gain"])

    def test_completely_neutral_rounds_accept_until_three_round_cap(self):
        result = self.run_controller([review(5)] * 4)
        self.assertEqual(result["generation"].call_count, 3)
        self.assertEqual(result["peer"].call_count, 4)
        self.assertEqual(result["final_tex"], "candidate tex 3")
        self.assertEqual(len(result["agent"].worklogs), 3)

    def test_confidence_drops_are_excluded_from_gain_drop_calculation(self):
        result = self.run_controller([review(5, confidence=5), review(5, confidence=1)], max_reflections=1)
        log = result["agent"].worklogs["v1"]
        self.assertEqual(log["outcome"], "ACCEPTED_NEUTRAL_IMPROVEMENT")
        self.assertEqual(log["total_drop"], 0)
        self.assertNotIn("Confidence", log["deltas"])

    def test_compile_failure_consumes_round_and_next_round_uses_previous_version(self):
        result = self.run_controller([review(5), review(6)],
                                     fail_compile={"refined_paper_v1", "refined_paper_v3"})
        self.assertEqual(result["generation"].call_count, 3)
        self.assertEqual(result["peer"].call_count, 2)
        self.assertEqual(result["final_tex"], "candidate tex 2")
        self.assertEqual(set(result["agent"].worklogs), {"v2"})
        second = result["generation"].call_args_list[1].kwargs["contents"][1].text
        self.assertIn("baseline tex", second)
        self.assertNotIn("candidate tex 1", second)

    def test_empty_latex_stops_without_compile_or_candidate_review(self):
        result = self.run_controller([review(5)], responses=[{"parsed_response": '{"json": {}, "latex": null}'}])
        self.assertEqual(result["generation"].call_count, 1)
        self.assertEqual(result["peer"].call_count, 1)
        self.assertEqual(result["compilations"], ["initial_draft"])
        self.assertEqual(result["final_tex"], "baseline tex")

    def test_generation_exception_stops_immediately_and_formatting_still_runs(self):
        result = self.run_controller([review(5)], response_error=RuntimeError("provider unavailable"))
        self.assertEqual(result["generation"].call_count, 1)
        self.assertEqual(result["format"].call_count, 1)
        self.assertEqual(result["final_tex"], "baseline tex")

    def test_invalid_json_stops_instead_of_silently_advancing(self):
        result = self.run_controller([review(5)], responses=[{"parsed_response": "not json"}])
        self.assertEqual(result["generation"].call_count, 1)
        self.assertEqual(result["peer"].call_count, 1)
        self.assertEqual(result["final_tex"], "baseline tex")

    def test_one_formatting_fix_accepts_on_compile_without_peer_rereview(self):
        formatting = {"figure_and_tables": {"Figure 1": {"detected_issue": "overflows margin"}}}
        result = self.run_controller([review(5)], max_reflections=0,
                                     formatting=formatting,
                                     responses=[{"raw_response": "```latex\nformatted tex\n```"}])
        self.assertEqual(result["format"].call_count, 1)
        self.assertEqual(result["peer"].call_count, 1)
        self.assertEqual(result["generation"].call_count, 1)
        self.assertEqual(result["final_tex"], "formatted tex")
        self.assertEqual(result["final_pdf"], b"formatted tex")
        self.assertEqual(result["agent"].format_worklogs["v1"]["outcome"], "ACCEPTED_COMPILE_SUCCESS")

    def test_format_compile_failure_retains_content_version(self):
        result = self.run_controller([review(5)], max_reflections=0,
                                     formatting={"other_issues": ["bad spacing"]},
                                     responses=[{"raw_response": "formatted tex"}],
                                     fail_compile={"formatted_candidate_v1"})
        self.assertEqual(result["final_tex"], "baseline tex")
        self.assertEqual(result["final_pdf"], b"baseline tex")
        self.assertEqual(result["agent"].format_worklogs["v1"]["outcome"], "REJECTED_COMPILE_FAILURE")

    def test_format_review_error_is_preserved_as_upstream_no_issue_behavior(self):
        result = self.run_controller([review(5)], max_reflections=0, formatting={"Error": "vision failed"})
        self.assertEqual(result["generation"].call_count, 0)
        self.assertEqual(result["final_tex"], "baseline tex")

    def test_peer_review_failure_becomes_zero_score(self):
        tmp = self.quiet.enter_context(tempfile.TemporaryDirectory())
        agent = refinement_module.ContentRefinementAgent("missing", "missing", "missing", work_dir=tmp)
        with patch.object(refinement_module, "load_paper", side_effect=ValueError("bad PDF")):
            value, score = agent._get_peer_review("bad.pdf", "initial")
        self.assertEqual(score, 0)
        self.assertEqual(value["Overall"], 0)
        self.assertIn("bad PDF", value["Error"])


class LiteratureControllerTests(QuietTest):
    def make_agent(self):
        tmp = self.quiet.enter_context(tempfile.TemporaryDirectory())
        root = Path(tmp)
        inputs = []
        for name in ["idea.md", "experimental_log.md", "template.tex", "guidelines.md"]:
            path = root / name
            path.write_text(name + " sentinel")
            inputs.append(str(path))
        return literature_module.HybridLiteratureAgent(*inputs, output_dir=str(root / "literature")), root

    @staticmethod
    def outline():
        return {"intro_related_work_plan": {
            "introduction_strategy": {"search_directions": ["intro query"], "problem_gap_hypothesis": "gap"},
            "related_work_strategy": {"subsections": [{"subsection_title": "Related", "methodology_cluster": "cluster"}]}},
            "section_plan": [{"section_title": "Method", "subsections": [{"subsection_title": "Core",
                  "content_bullets": ["a", "b"], "citation_hints": ["specific primary paper"]}]}]}

    def test_search_tasks_preserve_intro_related_and_targeted_context(self):
        agent, _ = self.make_agent()
        tasks = agent._collect_search_tasks(self.outline())
        self.assertEqual([(t["section"], t["focus"], t["search_type"]) for t in tasks], [
            ("Introduction", "intro query", "exploration"),
            ("Related Work: Related", "Related cluster", "exploration"),
            ("Method - Core", "specific primary paper", "targeted")])
        self.assertIn("a b", tasks[2]["context"])

    def test_distinct_searches_overlap_duplicates_run_once_then_enrichment_is_sequential(self):
        agent, _ = self.make_agent()
        barrier = threading.Barrier(2)
        events = []
        lock = threading.Lock()
        task1 = {"section": "Introduction", "focus": "one"}
        task2 = {"section": "Related Work", "focus": "two"}

        def search(task, outline, cutoff):
            with lock:
                events.append(("search-start", task["focus"], threading.get_ident()))
            barrier.wait(timeout=3)
            with lock:
                events.append(("search-end", task["focus"], threading.get_ident()))
            return [{"title": task["focus"]}]

        def enrich(cand, task, registry, cutoff):
            events.append(("enrich", cand["title"], threading.get_ident()))

        processed = set()
        with patch.object(agent, "_process_search_task_google", side_effect=search) as searches, \
             patch.object(agent, "_enrich_and_register_paper", side_effect=enrich) as enriches, \
             patch("time.sleep") as sleep:
            agent._execute_tasks_in_parallel([task1, task1, task2], {}, {}, processed, "2024-11")
            agent._execute_tasks_in_parallel([task1, task2], {}, {}, processed, "2024-11")
        self.assertEqual(searches.call_count, 2)
        self.assertEqual(enriches.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual({c.args[0] for c in sleep.call_args_list}, {1.0})
        self.assertEqual(len({e[2] for e in events if e[0] == "search-start"}), 2)
        self.assertEqual(len({e[2] for e in events if e[0] == "enrich"}), 1)
        self.assertTrue(all(e[0] != "enrich" for e in events[:4]))
        self.assertEqual(processed, {"Introduction:one", "Related Work:two"})

    def test_empty_or_failed_discovery_gets_exactly_three_attempts(self):
        agent, _ = self.make_agent()
        task = {"section": "Introduction", "focus": "test"}
        with patch.object(agent, "_discover_candidates", side_effect=[[], RuntimeError("failed"), []]) as discovery:
            self.assertEqual(agent._process_search_task_google(task, {}, "2024-11"), [])
        self.assertEqual(discovery.call_count, 3)

    def test_discovery_success_stops_retries(self):
        agent, _ = self.make_agent()
        task = {"section": "Introduction", "focus": "test"}
        with patch.object(agent, "_discover_candidates", side_effect=[[], [{"title": "found"}]]) as discovery:
            self.assertEqual(agent._process_search_task_google(task, {}, "2024-11"), [{"title": "found"}])
        self.assertEqual(discovery.call_count, 2)

    def test_discovery_uses_search_tool_and_preserves_hardcoded_model_temperatures(self):
        agent, _ = self.make_agent()
        for kind, temperature in [("targeted", .1), ("exploration", .4)]:
            with self.subTest(kind=kind), patch.object(literature_module, "call_gemini_with_contents",
                   return_value={"parsed_response": {"candidates": [{"title": "found"}]}}) as call:
                candidates = agent._discover_candidates({"section": "s", "focus": "f", "context": "c", "search_type": kind}, {}, "2024-11")
                self.assertEqual(candidates, [{"title": "found"}])
                self.assertEqual(call.call_args.kwargs["model_name"], "gemini-3-flash-preview")
                self.assertEqual(call.call_args.kwargs["generation_configs"]["temperature"], temperature)
                self.assertEqual(len(call.call_args.kwargs["generation_configs"]["tools"]), 1)

    def test_bibliography_collision_mutates_keys_before_map_and_outline_injection(self):
        agent, root = self.make_agent()
        papers = [literature_module.PaperData(citation_key="Same2020Key", title="Paper " + str(i),
                   authors=["A Author"], venue="Venue", year=2020, abstract="Abstract " + str(i),
                   citation_count=0, found_in_section=section, reason="relevant")
                  for i, section in enumerate(["Introduction", "Method - Core"])]
        outline_path = root / "outline.json"
        outline_path.write_text(json.dumps(self.outline()))

        def enrich(tasks, outline, registry, processed, cutoff):
            registry.update({"p1": papers[0], "p2": papers[1]})

        with patch.object(agent, "_execute_tasks_in_parallel", side_effect=enrich), \
             patch.object(agent, "_synthesize_content", return_value="LITERATURE_FILLED_TEMPLATE") as synthesis:
            agent.run(str(outline_path), "2024-11")
        out = Path(agent.output_dir)
        mapping = json.loads((out / "citation_map.json").read_text())
        updated = json.loads((out / "outline_v1.json").read_text())
        self.assertEqual(set(mapping), {"Same2020Key", "Same2020Keya"})
        self.assertIn("@inproceedings{Same2020Keya,", (out / "references.bib").read_text())
        method = updated["section_plan"][0]["subsections"][0]
        self.assertEqual(method["citation_candidates"], ["Same2020Keya"])
        self.assertNotIn("citation_hints", method)
        self.assertEqual(updated["intro_related_work_plan"]["introduction_strategy"]["citation_candidates"], ["Same2020Key"])
        self.assertEqual((out / "updated_template.tex").read_text(), "LITERATURE_FILLED_TEMPLATE")
        self.assertEqual(synthesis.call_args.args[1][1].citation_key, "Same2020Keya")

    def test_enrichment_dedup_keeps_first_section_and_requires_abstract(self):
        agent, _ = self.make_agent()
        candidate = {"title": "Same Title", "year": 2020, "reason": "useful"}
        metadata = {"title": "Same Title", "authors": [{"name": "A Author"}], "year": 2020,
                    "abstract": "A real abstract", "venue": "Venue"}
        registry = {}
        with patch.object(literature_module, "s2_title_search", return_value=metadata) as search:
            agent._enrich_and_register_paper(candidate, {"section": "Introduction"}, registry, "2024-11")
            agent._enrich_and_register_paper(candidate, {"section": "Method - Core"}, registry, "2024-11")
        self.assertEqual(search.call_count, 1)
        self.assertEqual(next(iter(registry.values())).found_in_section, "Introduction")
        with patch.object(literature_module, "s2_title_search", return_value={**metadata, "abstract": ""}):
            no_abstract = {}
            agent._enrich_and_register_paper(candidate, {"section": "Introduction"}, no_abstract, "2024-11")
        self.assertEqual(no_abstract, {})


class PipelineHandoffTests(QuietTest):
    def setup_pipeline(self):
        tmp = self.quiet.enter_context(tempfile.TemporaryDirectory())
        root = Path(tmp)
        base = root / "run"
        materials = base / "raw_materials"
        materials.mkdir(parents=True)
        (materials / "idea_dense.md").write_text("idea")
        (materials / "experimental_log.md").write_text("raw experiment")
        template = root / "template"
        template.mkdir()
        (template / "template.tex").write_text("original template")
        (template / "guidelines.md").write_text("guidelines")
        return base, template

    def fakes(self, base, *, parallel=False, outline_failures=0):
        events = []
        barrier = threading.Barrier(2) if parallel else None
        state = {"outline_calls": 0, "literature_done": False, "plot_done": not parallel}
        testcase = self

        class Outline:
            def __init__(self, **kwargs):
                pass
            def run(self, **kwargs):
                state["outline_calls"] += 1
                events.append("outline")
                if state["outline_calls"] <= outline_failures:
                    raise RuntimeError("transient outline failure")
                Path(kwargs["output_filepath"]).write_text('{"stage":"initial outline"}')

        class Literature:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
            def run(self, **kwargs):
                testcase.assertEqual(json.loads(Path(kwargs["outline_path"]).read_text())["stage"], "initial outline")
                events.append("literature-start")
                if barrier:
                    barrier.wait(timeout=3)
                out = Path(self.kwargs["output_dir"])
                out.mkdir(parents=True, exist_ok=True)
                for name, content in [("outline_v1.json", '{"stage":"enriched outline"}'),
                                      ("updated_template.tex", "intro and related work filled"),
                                      ("references.bib", "real bibliography"),
                                      ("citation_map.json", '{"key":{"title":"real title"}}')]:
                    (out / name).write_text(content)
                state["literature_done"] = True
                events.append("literature-end")

        class Plotting:
            def __init__(self, **kwargs):
                pass
            def run(self, **kwargs):
                testcase.assertEqual(json.loads(Path(kwargs["outline_json_path"]).read_text())["stage"], "initial outline")
                events.append("plot-start")
                barrier.wait(timeout=3)
                (base / "figures").mkdir(exist_ok=True)
                (base / "figures" / "plot.jpg").write_bytes(b"raster figure")
                state["plot_done"] = True
                events.append("plot-end")
                return [{"image_path": "figures/plot.jpg", "caption": "plot caption"}]

        class Section:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
            def run(self, **kwargs):
                events.append("section")
                testcase.assertTrue(state["literature_done"])
                testcase.assertTrue(state["plot_done"])
                testcase.assertEqual(Path(self.kwargs["template_path"]).read_text(), "intro and related work filled")
                testcase.assertEqual(json.loads(Path(self.kwargs["outline_path"]).read_text())["stage"], "enriched outline")
                testcase.assertEqual(json.loads(Path(self.kwargs["citation_map_path"]).read_text())["key"]["title"], "real title")
                testcase.assertEqual((base / "latex_writeup" / "references.bib").read_text(), "real bibliography")
                if parallel:
                    testcase.assertEqual(json.loads(Path(self.kwargs["figures_info_path"]).read_text()), [{"name": "plot.jpg", "caption": "plot caption"}])
                    testcase.assertEqual((base / "latex_writeup" / "figures" / "plot.jpg").read_bytes(), b"raster figure")
                Path(kwargs["output_path"]).write_text("completed full draft")

        class Refinement:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                testcase.assertEqual(kwargs["max_reflections"], 3)
            def run(self, **kwargs):
                events.append("refinement")
                testcase.assertEqual(Path(kwargs["texfile_path"]).read_text(), "completed full draft")
                work = Path(self.kwargs["work_dir"])
                testcase.assertEqual((work / "raw_draft_paper.tex").read_text(), "completed full draft")
                out = work / "final_refined_paper.pdf"
                out.write_bytes(b"compiled final paper")
                return str(out)

        return {"OutlineAgent": Outline, "HybridLiteratureAgent": Literature,
                "SectionWritingAgent": Section, "ContentRefinementAgent": Refinement,
                "PlottingAgent": Plotting}, events, state

    def test_all_literature_artifacts_handoff_before_section_and_refinement(self):
        base, template = self.setup_pipeline()
        fakes, events, _ = self.fakes(base)
        fakes.pop("PlottingAgent")
        with patch.multiple(paper_writer, **fakes):
            success = paper_writer.write_single_paper(str(base), str(template))
        self.assertTrue(success)
        self.assertEqual(events, ["outline", "literature-start", "literature-end", "section", "refinement"])
        self.assertEqual((base / "final_paper.pdf").read_bytes(), b"compiled final paper")

    def test_plot_and_literature_run_in_parallel_and_both_join_before_section(self):
        base, template = self.setup_pipeline()
        fakes, events, _ = self.fakes(base, parallel=True)
        with patch.multiple(paper_writer_with_plotting, **fakes):
            success = paper_writer_with_plotting.write_single_paper(str(base), str(template))
        self.assertTrue(success)
        self.assertLess(events.index("literature-start"), events.index("plot-end"))
        self.assertLess(events.index("plot-start"), events.index("literature-end"))
        self.assertLess(events.index("literature-end"), events.index("section"))
        self.assertLess(events.index("plot-end"), events.index("section"))
        self.assertEqual((base / "final_paper.pdf").read_bytes(), b"compiled final paper")

    def test_outer_retry_restarts_outline_and_stops_on_third_success(self):
        base, template = self.setup_pipeline()
        fakes, events, state = self.fakes(base, outline_failures=2)
        fakes.pop("PlottingAgent")
        with patch.multiple(paper_writer, **fakes):
            success = paper_writer.write_single_paper(str(base), str(template))
        self.assertTrue(success)
        self.assertEqual(state["outline_calls"], 3)
        self.assertEqual(events[:3], ["outline"] * 3)
        self.assertEqual(events.count("section"), 1)

    def test_outer_retry_exhausts_at_three_and_reports_failure(self):
        base, template = self.setup_pipeline()
        fakes, events, state = self.fakes(base, outline_failures=99)
        fakes.pop("PlottingAgent")
        with patch.multiple(paper_writer, **fakes):
            success = paper_writer.write_single_paper(str(base), str(template))
        self.assertFalse(success)
        self.assertEqual(state["outline_calls"], 3)
        self.assertEqual(events, ["outline"] * 3)
        self.assertFalse((base / "final_paper.pdf").exists())


class SectionInputHandoffTests(QuietTest):
    def test_prompt_contains_all_handoff_truth_and_only_existing_raster_images(self):
        tmp = self.quiet.enter_context(tempfile.TemporaryDirectory())
        root = Path(tmp)
        paths = {}
        for name, value in [("outline.json", '{"outline_sentinel": true}'),
                            ("template.tex", "EXISTING_INTRO_SENTINEL"),
                            ("idea.md", "METHOD_SENTINEL"),
                            ("experimental_log.md", "DATA_SENTINEL"),
                            ("guidelines.md", "GUIDELINE_SENTINEL"),
                            ("citation_map.json", json.dumps({"ExactKey": {
                                "title": "REFERENCE_TITLE_SENTINEL", "authors": ["A Author"],
                                "year": 2020, "abstract": "REFERENCE_ABSTRACT_SENTINEL"}}))]:
            paths[name] = root / name
            paths[name].write_text(value)
        figures = root / "figures"
        figures.mkdir()
        (figures / "raster.png").write_bytes(b"raster")
        (figures / "vector.pdf").write_bytes(b"PDF")
        (figures / "info.json").write_text(json.dumps([
            {"name": "raster.png", "caption": "RASTER_CAPTION_SENTINEL"},
            {"name": "vector.pdf", "caption": "VECTOR_CAPTION_SENTINEL"},
            {"name": "missing.jpg", "caption": "MISSING_CAPTION_SENTINEL"}]))
        agent = section_module.SectionWritingAgent(
            str(paths["outline.json"]), str(paths["template.tex"]),
            str(paths["idea.md"]), str(paths["experimental_log.md"]),
            str(paths["citation_map.json"]), str(figures / "info.json"),
            str(paths["guidelines.md"]))
        with patch.object(section_module, "call_llm_with_images", return_value={"parsed_response": "FULL_LATEX_SENTINEL"}) as call:
            returned = agent.run(str(root / "draft.tex"))
        kwargs = call.call_args.kwargs
        for value in ["outline_sentinel", "EXISTING_INTRO_SENTINEL", "METHOD_SENTINEL",
                      "DATA_SENTINEL", "GUIDELINE_SENTINEL", "ExactKey", "REFERENCE_TITLE_SENTINEL",
                      "REFERENCE_ABSTRACT_SENTINEL", "raster.png", "vector.pdf", "missing.jpg",
                      "RASTER_CAPTION_SENTINEL", "VECTOR_CAPTION_SENTINEL"]:
            self.assertIn(value, kwargs["prompt"])
        self.assertEqual(kwargs["images"], [str(figures / "raster.png")])
        self.assertEqual(returned, "FULL_LATEX_SENTINEL")
        self.assertEqual((root / "draft.tex").read_text(), "FULL_LATEX_SENTINEL")


class FigureCriticControllerTests(QuietTest):
    def run_figure(self, critiques, generated, *, max_rounds=3):
        tmp = self.quiet.enter_context(tempfile.TemporaryDirectory())
        root = Path(tmp)
        (root / "experimental_log.md").write_text("QUANTITATIVE_TRUTH_SENTINEL")
        plan = {"figure_id": "Figure 1", "title": "Measurements", "plot_type": "statistical chart",
                "objective": "compare measurements", "data_source": "experimental_log.md", "aspect_ratio": "4:3"}
        funcs = {"retrieve_few_shot_examples": Mock(return_value=[{"id": "example"}]),
                 "predict_figure_content": Mock(return_value="initial description"),
                 "style_figure_content": Mock(return_value="styled description"),
                 "generate_figure_visuals": Mock(side_effect=generated),
                 "critique_and_revise_figure": Mock(side_effect=critiques),
                 "generate_figure_caption": Mock(return_value="Final caption")}
        with patch.multiple(plotting_module, **funcs):
            result = plotting_module.process_single_figure(plan, str(root), max_critic_rounds=max_rounds)
        return result, funcs

    def test_no_changes_stops_after_first_critic_and_caption_uses_final_visual(self):
        result, funcs = self.run_figure([("same", "No changes needed.")], ["first image"])
        self.assertEqual(funcs["critique_and_revise_figure"].call_count, 1)
        self.assertEqual(funcs["generate_figure_visuals"].call_count, 1)
        self.assertEqual(result["description"], "styled description")
        self.assertEqual(result["task_name"], "plot")
        self.assertEqual(result["aspect_ratio"], "4:3")
        self.assertEqual(funcs["generate_figure_caption"].call_args.kwargs["base64_image"], "first image")
        self.assertIn("QUANTITATIVE_TRUTH_SENTINEL", funcs["predict_figure_content"].call_args.kwargs["raw_content"])

    def test_critic_revision_handoff_regenerates_and_caps_at_three(self):
        result, funcs = self.run_figure([("revised 1", "fix"), ("revised 2", "fix"), ("revised 3", "fix")],
                                        ["initial image", "image 1", "image 2", "image 3"])
        self.assertEqual(funcs["critique_and_revise_figure"].call_count, 3)
        self.assertEqual(funcs["generate_figure_visuals"].call_count, 4)
        self.assertEqual(result["description"], "revised 3")
        self.assertEqual(result["base64_img"], "image 3")
        self.assertEqual([c.kwargs["round_idx"] for c in funcs["critique_and_revise_figure"].call_args_list], [0, 1, 2])
        self.assertEqual(funcs["critique_and_revise_figure"].call_args_list[1].kwargs["figure_desc"], "revised 1")
        self.assertEqual(funcs["critique_and_revise_figure"].call_args_list[1].kwargs["base64_image"], "image 1")

    def test_failed_regeneration_retains_previous_image_and_new_description(self):
        result, funcs = self.run_figure([("revised", "fix"), ("revised", "No changes needed.")],
                                        ["valid previous image", None])
        self.assertEqual(result["description"], "revised")
        self.assertEqual(result["base64_img"], "valid previous image")
        self.assertEqual(funcs["generate_figure_caption"].call_args.kwargs["figure_desc"], "revised")

    def test_critic_exception_stops_but_caption_still_runs(self):
        result, funcs = self.run_figure([RuntimeError("critic unavailable")], ["valid image"])
        self.assertEqual(funcs["critique_and_revise_figure"].call_count, 1)
        self.assertEqual(funcs["generate_figure_caption"].call_count, 1)
        self.assertEqual(result["base64_img"], "valid image")
        self.assertEqual(result["critic_history"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
