"""Selected-source manuscript provenance tests; all model/render records are fixtures.

These tests exercise provenance assembly and actual upstream manuscript
controllers. External inference/review and compilation effects are controlled.
"""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper-orchestra/vendor"))
import orchestra_provenance as provenance
import orchestra_runtime as runtime_module
from orchestra_runtime import Runtime, configure, instrument
from methods.agents import content_refinement_agent as refinement_module
from methods.agents import section_writing_agent as section_module


ARITHMETIC = "x <- c(-2,-1,0,1,2)\ny <- 2*x+3\nmean(y-2*x)"


def manuscript(label="initial"):
    return (r"\documentclass{article}" + "\n"
            + r"\begin{filecontents*}[overwrite]{fig_intercept_error.R}" + "\n"
            + "library(ggplot2)\np <- ggplot(data.frame(x=1,y=2),aes(x,y)) + geom_point()\n"
            + r"\end{filecontents*}" + "\n"
            + r"\begin{filecontents*}{fig_residual_workflow.tex}" + "\n"
            + r"\documentclass[tikz]{standalone}\begin{document}\begin{tikzpicture}\node{Alternative};\end{tikzpicture}\end{document}" + "\n"
            + r"\end{filecontents*}" + "\n"
            + r"\begin{filecontents*}{reproduce_experiment.R}" + "\n" + ARITHMETIC + "\n"
            + r"\end{filecontents*}" + "\n"
            + r"\begin{document}" + "\n" + label + "\n"
            + r"\begin{figure}\includegraphics{figures/fig_intercept_error.jpg}\caption{Measured errors.}\label{fig:error}\end{figure}" + "\n"
            + r"\begin{figure}\includegraphics{figures/fig_residual_workflow.jpg}\caption{Finite calculation.}\label{fig:workflow}\end{figure}" + "\n"
            + r"\begin{verbatim}" + "\n" + ARITHMETIC + "\n" + r"\end{verbatim}" + "\n"
            + r"\end{document}")


class ProvenanceFixture:
    """Hash-labelled render artifacts; engine rendering is tested elsewhere."""
    def setUp(self):
        super().setUp()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.base = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        (self.base / "execution").mkdir()
        self.events = []
        self.results = []
        self.plot_id = "fig_intercept_error"
        self.diagram_id = "fig_residual_workflow"
        self.chosen = self.render(self.plot_id, "chosen-old", "ggplot2", b"selected plot preview")
        self.unselected = self.render(self.plot_id, "newer-unselected", "ggplot2", b"newer unselected preview")
        self.diagram = self.render(self.diagram_id, "diagram", "tikz", b"selected diagram preview")
        self.select(self.plot_id, self.chosen)
        self.select(self.diagram_id, self.diagram)
        self.flush()

    def render(self, figure_id, directory_name, backend, preview):
        directory = self.base / "figure_sources" / directory_name
        directory.mkdir(parents=True)
        name = "source.R" if backend == "ggplot2" else "source.tex"
        source = ("# LABELLED selected-source fixture " + directory_name + "\np <- 1\n" if backend == "ggplot2"
                  else r"\documentclass[tikz]{standalone}\begin{document}\begin{tikzpicture}\node{Selected};\end{tikzpicture}\end{document}")
        (directory / name).write_text(source)
        (directory / "preview.jpg").write_bytes(preview)
        (directory / "figure.pdf").write_bytes(b"%PDF labelled render fixture " + directory_name.encode())
        files = {name: provenance.sha(directory / name)}
        if backend == "ggplot2":
            (directory / "worker.R").write_text('set.seed(0)\nsource("source.R")\n')
            (directory / "sessionInfo.txt").write_text("LABELLED R SESSION FIXTURE")
            files["worker.R"] = provenance.sha(directory / "worker.R")
        metadata = {"backend": backend, "figure_id": figure_id, "source": name,
                    "status": "rendered", "source_sha256": provenance.sha(directory / name),
                    "files_sha256": files, "preview_sha256": provenance.sha(directory / "preview.jpg"),
                    "pdf_sha256": provenance.sha(directory / "figure.pdf")}
        (directory / "render.json").write_text(json.dumps(metadata))
        self.events.append({"event": "render_end", "figure_id": figure_id,
                            "directory": str(directory), "backend": backend, "source": name,
                            "source_sha256": metadata["source_sha256"], "pdf_sha256": metadata["pdf_sha256"],
                            "preview_sha256": metadata["preview_sha256"]})
        return directory

    def select(self, figure_id, directory):
        relative = "figures/" + figure_id + ".jpg"
        image = self.base / relative
        image.parent.mkdir(exist_ok=True)
        shutil.copyfile(directory / "preview.jpg", image)
        self.results.append({"figure_id": figure_id, "image_path": relative,
                             "task_name": "plot" if figure_id == self.plot_id else "diagram"})

    def flush(self):
        (self.base / "execution/trace.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.events))
        (self.base / "plotting_results.json").write_text(json.dumps(self.results))

    def build(self):
        return provenance.build_manifest(self.base)

    def assert_canonical(self, tex, manifest):
        self.assertEqual(tex.count(provenance.BEGIN), 1)
        self.assertEqual(tex.count(provenance.END), 1)
        simplified = (tex.replace(r"\allowbreak{}", "").replace(r"\_", "_")
                      .replace(r"\char95{}", "_"))
        for item in manifest["figures"]:
            self.assertIn(item["source"], simplified)
            self.assertIn(item["source_sha256"], simplified)
        self.assertIn("figure_provenance.json", simplified)
        self.assertIn(ARITHMETIC, tex)
        self.assertNotIn("ggplot(", tex)
        self.assertNotIn(r"\begin{tikzpicture}", tex)
        provenance.verify_manuscript(tex, manifest)


class ManifestTests(ProvenanceFixture, unittest.TestCase):
    def test_selects_prior_success_by_preview_not_newest_render_directory(self):
        manifest = self.build()
        item = next(i for i in manifest["figures"] if i["figure_id"] == self.plot_id)
        self.assertEqual(item["original_directory"], "figure_sources/chosen-old")
        self.assertEqual((self.base / item["source"]).read_bytes(), (self.chosen / "source.R").read_bytes())
        self.assertNotEqual((self.base / item["source"]).read_bytes(), (self.unselected / "source.R").read_bytes())
        self.assertIn("figure_code/fig_intercept_error/worker.R", item["files"])
        self.assertTrue((self.base / "figure_provenance.json").is_file())

    def test_equal_preview_bytes_across_concurrent_ids_keep_correct_sources(self):
        # Hash equality alone must never select another figure's source.
        (self.diagram / "preview.jpg").write_bytes((self.chosen / "preview.jpg").read_bytes())
        metadata = json.loads((self.diagram / "render.json").read_text())
        metadata["preview_sha256"] = provenance.sha(self.diagram / "preview.jpg")
        (self.diagram / "render.json").write_text(json.dumps(metadata))
        self.events[-1]["preview_sha256"] = metadata["preview_sha256"]
        shutil.copyfile(self.diagram / "preview.jpg", self.base / self.results[-1]["image_path"])
        self.flush()
        manifest = self.build()
        by_id = {i["figure_id"]: i for i in manifest["figures"]}
        self.assertEqual(by_id[self.plot_id]["backend"], "ggplot2")
        self.assertEqual(by_id[self.diagram_id]["backend"], "tikz")
        self.assertEqual(by_id[self.diagram_id]["original_directory"], "figure_sources/diagram")

    def test_publish_copies_exact_aliases_and_manifest(self):
        manifest = self.build()
        workspace = self.base / "writeup"
        self.assertEqual(provenance.publish_workspace(self.base, workspace), manifest)
        self.assertEqual((workspace / "figure_provenance.json").read_bytes(), (self.base / "figure_provenance.json").read_bytes())
        for item in manifest["figures"]:
            for name in item["files"]:
                self.assertEqual((workspace / name).read_bytes(), (self.base / name).read_bytes())
        provenance.verify_files(workspace, manifest)

    def test_selected_renderer_input_tampering_is_rejected(self):
        (self.chosen / "worker.R").write_text("tampered original wrapper")
        with self.assertRaises(provenance.ProvenanceError):
            self.build()

    def test_published_alias_tamper_cannot_be_silently_republished(self):
        manifest = self.build()
        (self.base / manifest["figures"][0]["source"]).write_text("tampered source alias")
        with self.assertRaises(provenance.ProvenanceError):
            provenance.publish_workspace(self.base, self.base / "workspace")

    def test_workspace_tampering_is_detected(self):
        manifest = self.build()
        workspace = self.base / "workspace"
        provenance.publish_workspace(self.base, workspace)
        (workspace / manifest["figures"][0]["source"]).write_text("tampered published code")
        with self.assertRaises(provenance.ProvenanceError):
            provenance.verify_files(workspace, manifest)

    def test_missing_successful_context_for_selected_image_is_rejected(self):
        self.events = [e for e in self.events if e["directory"] != str(self.chosen)]
        self.flush()
        with self.assertRaisesRegex(provenance.ProvenanceError, "successful"):
            self.build()


class NormalizationTests(ProvenanceFixture, unittest.TestCase):
    def test_removes_figure_recipes_preserves_arithmetic_and_is_idempotent(self):
        manifest = self.build()
        effective, removed = provenance.normalize_latex(manuscript(), manifest)
        self.assertEqual(set(removed), {"fig_intercept_error.R", "fig_residual_workflow.tex"})
        self.assertIn(r"\begin{filecontents*}{reproduce_experiment.R}", effective)
        self.assert_canonical(effective, manifest)
        twice, removed_again = provenance.normalize_latex(effective, manifest)
        self.assertEqual(twice, effective)
        self.assertEqual(removed_again, [])

    def test_incomplete_empty_and_non_manuscript_outputs_are_preserved(self):
        manifest = self.build()
        for value in [None, "", "   ", r"\begin{document}incomplete", "No LaTeX generated."]:
            with self.subTest(value=value):
                self.assertEqual(provenance.normalize_latex(value, manifest), (value, []))

    def test_section_result_is_normalized_before_consumption_and_input_unchanged(self):
        manifest = self.build()
        raw = manuscript("section output")
        original = {"raw_response": "```latex\n" + raw + "\n```", "parsed_response": raw}
        updated, details = provenance.transform_result(original, manifest)
        self.assertEqual(details["kind"], "section")
        self.assert_canonical(updated["parsed_response"], manifest)
        self.assertIn(provenance.BEGIN, updated["raw_response"])
        self.assertNotIn(provenance.BEGIN, original["parsed_response"])

    def test_content_json_string_wrapper_preserves_worklog_and_normalizes_latex(self):
        manifest = self.build()
        worklog = {"addressed_weaknesses": ["fixture"], "actions_taken": ["keep exact data"]}
        tex = manuscript("revision output")
        original = {"raw_response": "```json\n" + json.dumps(worklog) + "\n```\n```latex\n" + tex + "\n```",
                    "parsed_response": json.dumps({"json": worklog, "latex": tex})}
        updated, details = provenance.transform_result(original, manifest)
        parsed = json.loads(updated["parsed_response"])
        self.assertEqual(details["kind"], "content")
        self.assertEqual(parsed["json"], worklog)
        self.assert_canonical(parsed["latex"], manifest)
        self.assertIn("```json\n" + json.dumps(worklog), updated["raw_response"])

    def test_format_raw_channel_and_nested_parser_channel_both_normalize(self):
        manifest = self.build()
        raw = "```latex\n" + manuscript("format output") + "\n```"
        updated, details = provenance.transform_result({"raw_response": raw, "parsed_response": {"raw_response": raw}}, manifest)
        self.assertEqual(details["kind"], "format")
        self.assertEqual(updated["raw_response"], updated["parsed_response"]["raw_response"])
        self.assertIn(provenance.BEGIN, updated["raw_response"])
        self.assertNotIn("ggplot(", updated["raw_response"])

    def test_empty_refinement_output_stays_empty_for_original_stopping_rule(self):
        manifest = self.build()
        original = {"raw_response": "No latex.", "parsed_response": json.dumps({"json": {"fixture": True}, "latex": None})}
        updated, details = provenance.transform_result(original, manifest)
        self.assertEqual(updated, original)
        self.assertIsNone(details)


class ControllerConsumptionTests(ProvenanceFixture, unittest.TestCase):
    """Use actual upstream controllers and runtime hooks, never a late final edit."""
    def setUp(self):
        super().setUp()
        from methods.agents.outline_agent import OutlineAgent
        from methods.agents.literature_review_agent import HybridLiteratureAgent
        from methods.agents.plotting_agent import PlottingAgent
        from utils import gemini_utils
        import requests
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(redirect_stderr(io.StringIO()))
        previous_runtime = runtime_module._runtime
        self.stack.callback(configure, previous_runtime)
        self.queue = []
        self.requests = []
        self.compiles = {}
        self.fail_compiles = set()

        def executor(command, prompt, directory):
            self.requests.append({"prompt": prompt, "directory": directory,
                                  "request": json.loads((directory / "request.json").read_text())})
            if not self.queue:
                raise AssertionError("No labelled response fixture remains")
            return self.queue.pop(0)

        self.runtime = Runtime(self.base / "execution", executor=executor, manuscript_provenance=True)
        configure(self.runtime)
        # All instrumentation hooks are restored on cleanup, including requests.
        for cls in [OutlineAgent, HybridLiteratureAgent, PlottingAgent,
                    section_module.SectionWritingAgent, refinement_module.ContentRefinementAgent]:
            self.stack.enter_context(patch.object(cls, "run", cls.run))
        self.stack.enter_context(patch.object(requests, "get", requests.get))
        self.stack.enter_context(patch.object(gemini_utils.time, "sleep", lambda *args: None))
        self.stack.enter_context(patch.object(refinement_module, "pdf_to_grid_images", lambda *args: []))

        def compile_fixture(cwd, pdf_path, basename="template", timeout=30):
            import pymupdf
            source = (Path(cwd) / (basename + ".tex")).read_text()
            self.compiles[basename] = {"tex": source, "pdf_path": str(pdf_path)}
            if basename in self.fail_compiles:
                return
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "LABELLED COMPILE FIXTURE: " + basename)
            page.insert_text((72, 95), hashlib.sha256(source.encode()).hexdigest())
            doc.save(pdf_path)
            doc.close()
            self.compiles[basename]["pdf_sha256"] = provenance.sha(pdf_path)

        self.stack.enter_context(patch.object(refinement_module, "compile_latex", compile_fixture))
        instrument(self.base)
        self.writeup = self.base / "latex_writeup"
        self.writeup.mkdir()
        self.materials = self.base / "raw_materials"
        self.materials.mkdir()
        (self.materials / "idea.md").write_text("LABELLED IDEA FIXTURE")
        (self.materials / "experimental_log.md").write_text(ARITHMETIC)
        (self.base / "outline.json").write_text('{"fixture":true}')
        (self.base / "citation_map.json").write_text("{}")
        (self.writeup / "template.tex").write_text(manuscript("template"))
        (self.writeup / "guidelines.md").write_text("LABELLED GUIDELINE FIXTURE")
        figures = self.writeup / "figures"
        figures.mkdir()
        info = []
        for item in self.results:
            image = Path(item["image_path"])
            shutil.copyfile(self.base / image, figures / image.name)
            info.append({"name": image.name, "caption": "LABELLED FIGURE FIXTURE"})
        (figures / "info.json").write_text(json.dumps(info))

    @staticmethod
    def rating(overall):
        result = {axis: 2 for axis in ["Originality", "Quality", "Clarity", "Significance",
                                      "Soundness", "Presentation", "Contribution"]}
        result.update(Overall=overall, Confidence=3)
        return result

    def section(self):
        self.queue.append("```latex\n" + manuscript("INITIAL_SECTION_FIXTURE") + "\n```")
        agent = section_module.SectionWritingAgent(
            str(self.base / "outline.json"), str(self.writeup / "template.tex"),
            str(self.materials / "idea.md"), str(self.materials / "experimental_log.md"),
            str(self.base / "citation_map.json"), str(self.writeup / "figures/info.json"),
            str(self.writeup / "guidelines.md"))
        draft = self.writeup / "raw_draft_paper.tex"
        agent.run(str(draft))
        self.manifest = self.runtime.figure_provenance
        self.assertIsNotNone(self.manifest)
        self.assert_canonical(draft.read_text(), self.manifest)
        return draft

    def refinement(self, draft, reviews, *, rounds=2, formatting=None):
        work = self.base / "content_refinement_workdir"
        shutil.copytree(self.writeup, work)
        agent = refinement_module.ContentRefinementAgent(
            str(self.materials / "experimental_log.md"), str(self.base / "citation_map.json"),
            str(self.writeup / "guidelines.md"), work_dir=str(work), max_reflections=rounds)
        peer = Mock(side_effect=[(self.rating(score), float(score)) for score in reviews])
        fmt = Mock(return_value=formatting or {"figure_and_tables": {}, "other_issues": []})
        with patch.object(agent, "_get_peer_review", peer), patch.object(agent, "_get_formatting_review", fmt):
            final_pdf = agent.run(str(draft))
        return agent, work, Path(final_pdf), peer, fmt

    @staticmethod
    def revision_response(label):
        plan = {"addressed_weaknesses": [label], "actions_taken": ["preserve arithmetic"]}
        return "```json\n" + json.dumps(plan) + "\n```\n```latex\n" + manuscript(label) + "\n```"

    def assert_context_published_to_each_worker(self):
        for invocation in self.requests:
            request, directory = invocation["request"], invocation["directory"]
            self.assertIn("[SELECTED FIGURE SOURCE PROVENANCE", invocation["prompt"])
            self.assertIn((self.chosen / "source.R").read_text(), invocation["prompt"])
            self.assertNotIn((self.unselected / "source.R").read_text(), invocation["prompt"])
            self.assertEqual(request["figure_provenance_sha256"], provenance.sha(directory / "figure_provenance.json"))
            for name, expected in request["figure_provenance_files"].items():
                self.assertEqual(provenance.sha(directory / name), expected)

    def test_initial_content_acceptance_and_reversion_use_already_effective_tex(self):
        draft = self.section()
        self.queue.extend([self.revision_response("ACCEPTED_V1_FIXTURE"),
                           self.revision_response("REJECTED_V2_FIXTURE")])
        agent, work, pdf, peer, fmt = self.refinement(draft, [3, 4, 3])
        self.assertEqual(peer.call_count, 3)
        self.assertEqual(fmt.call_count, 1)
        self.assertEqual(agent.worklogs["v1"]["outcome"], "ACCEPTED_SCORE_INCREASE")
        self.assertEqual(agent.worklogs["v2"]["outcome"], "REJECTED_SCORE_DECREASE")
        for basename, record in self.compiles.items():
            self.assert_canonical(record["tex"], self.manifest)
            self.assertEqual((work / (basename + ".tex")).read_text(), record["tex"])
        final_tex = (work / "final_refined_paper.tex").read_text()
        self.assertEqual(final_tex, self.compiles["refined_paper_v1"]["tex"])
        self.assertEqual(final_tex, agent.current_tex)
        self.assertIn("ACCEPTED_V1_FIXTURE", final_tex)
        self.assertNotIn("REJECTED_V2_FIXTURE", final_tex)
        self.assertEqual(provenance.sha(pdf), self.compiles["refined_paper_v1"]["pdf_sha256"])
        self.assertEqual(agent.worklogs["v1"]["agent_plan"], {"addressed_weaknesses": ["ACCEPTED_V1_FIXTURE"], "actions_taken": ["preserve arithmetic"]})
        self.assert_context_published_to_each_worker()

    def test_format_raw_channel_normalizes_before_single_compile_and_no_peer_rereview(self):
        draft = self.section()
        self.queue.append("```latex\n" + manuscript("FORMAT_EDITOR_FIXTURE") + "\n```")
        agent, work, pdf, peer, fmt = self.refinement(
            draft, [3], rounds=0, formatting={"other_issues": ["adjust spacing"]})
        self.assertEqual(peer.call_count, 1)
        self.assertEqual(fmt.call_count, 1)
        self.assertEqual(len(self.requests), 2)
        record = self.compiles["formatted_candidate_v1"]
        self.assert_canonical(record["tex"], self.manifest)
        self.assertEqual((work / "final_refined_paper.tex").read_text(), record["tex"])
        self.assertEqual(agent.current_tex, record["tex"])
        self.assertEqual(provenance.sha(pdf), record["pdf_sha256"])
        self.assertEqual(agent.format_worklogs["v1"]["outcome"], "ACCEPTED_COMPILE_SUCCESS")
        self.assert_context_published_to_each_worker()

    def test_empty_content_output_stops_without_creating_appendix_only_candidate(self):
        draft = self.section()
        self.queue.append('```json\n{"actions_taken":[]}\n```\nNo LaTeX supplied.')
        agent, work, pdf, peer, fmt = self.refinement(draft, [3])
        self.assertEqual(peer.call_count, 1)
        self.assertEqual(fmt.call_count, 1)
        self.assertEqual(set(self.compiles), {"initial_draft"})
        self.assertEqual(agent.worklogs, {})
        self.assertEqual((work / "final_refined_paper.tex").read_text(), draft.read_text())
        self.assertEqual(provenance.sha(pdf), self.compiles["initial_draft"]["pdf_sha256"])
        self.assertEqual(len(self.requests), 2)

    def test_compile_failure_consumes_round_without_reviewing_or_accepting_it(self):
        draft = self.section()
        self.fail_compiles.add("refined_paper_v1")
        self.queue.extend([self.revision_response("FAILED_COMPILE_V1"), self.revision_response("ACCEPTED_V2")])
        agent, work, pdf, peer, fmt = self.refinement(draft, [3, 4])
        self.assertEqual(peer.call_count, 2)
        self.assertEqual(set(agent.worklogs), {"v2"})
        self.assertEqual((work / "final_refined_paper.tex").read_text(), self.compiles["refined_paper_v2"]["tex"])
        self.assertEqual(provenance.sha(pdf), self.compiles["refined_paper_v2"]["pdf_sha256"])
        second_prompt = self.requests[2]["prompt"]
        self.assertIn("INITIAL_SECTION_FIXTURE", second_prompt)
        self.assertNotIn("FAILED_COMPILE_V1", second_prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
