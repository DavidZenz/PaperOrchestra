"""Independent provenance-auditor regressions using labelled recording fixtures.

No agent or R/TeX compiler is invoked. PDFs are synthetic PyMuPDF documents used
only to exercise visible-text checks; fixture events do not claim real inference.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "paper-orchestra"
sys.path.insert(0, str(SKILL / "vendor"))
import orchestra_provenance as provenance
from utils.gemini_utils import parse_gemini_latex_results, parse_gemini_json_latex_response
import pymupdf
from PIL import Image

SPEC = importlib.util.spec_from_file_location("paper_orchestra_provenance_auditor_test", SKILL / "scripts/audit_manuscript_provenance.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ProvenanceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paper-orchestra-provenance-audit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = []
        self.fig = "fixture_plot"
        original = self.root / "figure_sources/labelled-render-fixture"
        original.mkdir(parents=True)
        (original / "source.R").write_text('# LABELLED WORKER FIXTURE\nlibrary(ggplot2)\np <- ggplot(data.frame(x=1,y=2),aes(x,y))+geom_point()')
        (original / "worker.R").write_text('# LABELLED WRAPPER FIXTURE\nsource("source.R")\n')
        (original / "sessionInfo.txt").write_text("LABELLED R SESSION FIXTURE; no R process invoked")
        self.make_pdf(original / "figure.pdf", "LABELLED VECTOR ARTIFACT FIXTURE")
        Image.new("RGB", (80, 40), "white").save(original / "preview.jpg")
        self.metadata = {"backend": "ggplot2", "figure_id": self.fig, "source": "source.R", "status": "rendered",
                         "source_sha256": provenance.sha(original / "source.R"),
                         "pdf_sha256": provenance.sha(original / "figure.pdf"),
                         "preview_sha256": provenance.sha(original / "preview.jpg"),
                         "files_sha256": {name: provenance.sha(original / name) for name in ("source.R", "worker.R")}}
        (original / "render.json").write_text(json.dumps(self.metadata, indent=2))
        render_fields = {"figure_id": self.fig, "backend": "ggplot2", "directory": str(original),
                         "source_sha256": self.metadata["source_sha256"]}
        self.append("render_start", **render_fields)
        self.append("render_end", **render_fields, source="source.R", pdf_sha256=self.metadata["pdf_sha256"],
                    preview_sha256=self.metadata["preview_sha256"])
        (self.root / "figures").mkdir()
        shutil.copyfile(original / "preview.jpg", self.root / f"figures/{self.fig}.jpg")
        (self.root / "plotting_results.json").write_text(json.dumps([
            {"figure_id": self.fig, "task_name": "plot", "image_path": f"figures/{self.fig}.jpg"}]))
        execution = self.root / "execution"
        execution.mkdir()
        self.save_trace()
        self.manifest = provenance.build_manifest(self.root)
        for workspace in AUDIT.WORKSPACES:
            provenance.publish_workspace(self.root, self.root / workspace)
        self.manifest_sha = provenance.sha(self.root / "figure_provenance.json")
        self.append("provenance_published", stage="SectionWritingAgent", sha256=self.manifest_sha)
        self.calls = []
        self.compiles = []
        tex = (r"\documentclass{article}\begin{document}LABELLED MANUSCRIPT FIXTURE."
               r"\begin{figure}\includegraphics{figures/fixture_plot.jpg}\caption{Fixture}\label{fig:fixture}\end{figure}"
               r"\end{document}")
        section = self.add_manuscript("section-writer", "section", tex)
        self.add_compile("initial_draft", section)
        recipe = '\\begin{filecontents*}{alternative.R}\nlibrary(ggplot2)\np <- ggplot()\n\\end{filecontents*}\n'
        content = self.add_manuscript("content-or-format-editor", "content", recipe + tex.replace("MANUSCRIPT", "CONTENT"))
        self.add_compile("refined_paper_v1", content)
        formatted = self.add_manuscript("content-or-format-editor", "format", tex.replace("MANUSCRIPT", "FORMATTED"))
        self.add_compile("formatted_candidate_v1", formatted)
        final_tex = self.root / "content_refinement_workdir/final_refined_paper.tex"
        final_tex.write_text(AUDIT.result_tex(formatted))
        shutil.copyfile(self.compiles[-1]["pdf"], self.root / "final_paper.pdf")
        self.run = {"status": "completed", "manuscript_provenance": 1, "plotting": True,
                    "plot_backend": "ggplot2", "diagram_backend": "tikz", "artifacts": {}}
        self.reanchor()

    def append(self, event, **fields):
        value = {"seq": len(self.trace) + 1, "time": float(len(self.trace)), "event": event, **fields}
        self.trace.append(value)
        return value

    def save_trace(self):
        (self.root / "execution/trace.jsonl").write_text("".join(json.dumps(event) + "\n" for event in self.trace))

    def make_pdf(self, path, text, images=()):
        document = pymupdf.open()
        page = document.new_page(width=700, height=1000)
        page.insert_text((40, 40), text, fontsize=9)
        for index, image in enumerate(images):
            page.insert_image(pymupdf.Rect(40, 250 + index * 60, 120, 290 + index * 60),
                              stream=Path(image).read_bytes())
        document.save(path)
        document.close()

    def visible_text(self, title):
        lines = [title, "Figure source provenance"]
        for item in self.manifest["figures"]:
            lines += [item["source"], item["source_sha256"]]
            for name, checksum in item["files"].items():
                if name.endswith("/worker.R"):
                    lines += [name, checksum]
        return "\n".join(lines)

    def add_manuscript(self, role, kind, tex):
        call = f"labelled-call-{len(self.calls)}"
        invocation = f"labelled-invocation-{len(self.calls)}"
        directory = self.root / "execution/invocations" / invocation
        provenance.publish_workspace(self.root, directory)
        context = provenance.worker_context(self.root, self.manifest)
        (directory / "prompt.txt").write_text("LABELLED PROVENANCE AUDIT FIXTURE ONLY\n" + context)
        if kind == "content":
            worklog = {"actions_taken": ["Labelled fixture editorial action"]}
            raw = '```json\n' + json.dumps(worklog) + '\n```\n```latex\n' + tex + '\n```'
            parsed = parse_gemini_json_latex_response(raw)
        else:
            raw = '```latex\n' + tex + '\n```'
            parsed = {"raw_response": raw} if kind == "format" else parse_gemini_latex_results(raw)
        original = {"raw_response": raw, "parsed_response": parsed}
        effective, adaptation = provenance.transform_result(original, self.manifest)
        (directory / "response.txt").write_text(raw)
        native = [{"type": "thread.started", "thread_id": "labelled-session-" + call},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": raw}},
                  {"type": "turn.completed"}]
        (directory / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in native))
        request = {"role": role, "call": call, "invocation": invocation,
                   "figure_provenance_sha256": self.manifest_sha,
                   "figure_provenance_files": {name: value for item in self.manifest["figures"] for name, value in item["files"].items()},
                   "prompt_sha256": provenance.sha(directory / "prompt.txt")}
        (directory / "request.json").write_text(json.dumps(request))
        self.append("llm_call_start", call=call, role=role)
        start = self.append("agent_start", **request)
        self.append("process_started", invocation=invocation, pid=41000 + len(self.calls))
        end = self.append("agent_end", invocation=invocation, role=role, response_sha256=provenance.sha(directory / "response.txt"))
        manuscripts = self.root / "execution/manuscripts"
        manuscripts.mkdir(exist_ok=True)
        upstream = manuscripts / (call + ".upstream.json")
        downstream = manuscripts / (call + ".effective.json")
        upstream.write_text(json.dumps(original, indent=2))
        downstream.write_text(json.dumps(effective, indent=2))
        event = self.append("manuscript_result", call=call, role=role, original_path=str(upstream),
                            original_sha256=provenance.sha(upstream), effective_path=str(downstream),
                            effective_sha256=provenance.sha(downstream), provenance_sha256=self.manifest_sha, adaptation=adaptation)
        parsed_file = self.root / "execution/parsed" / (call + ".json")
        parsed_file.parent.mkdir(exist_ok=True)
        parsed_file.write_text(json.dumps(effective["parsed_response"], indent=2))
        call_end = self.append("llm_call_end", call=call, parsed_path=str(parsed_file), sha256=provenance.sha(parsed_file))
        self.calls.append({"call": call, "directory": directory, "start": start, "end": end,
                           "event": event, "call_end": call_end, "upstream": upstream,
                           "effective": downstream, "parsed_file": parsed_file})
        return effective

    def add_compile(self, name, result):
        tex = self.root / "content_refinement_workdir" / (name + ".tex")
        tex.write_text(AUDIT.result_tex(result))
        snapshot = self.root / "execution/compiled" / ("labelled-" + str(len(self.compiles)) + "-" + name)
        provenance.publish_workspace(self.root, snapshot)
        source_snapshot = snapshot / "source.tex"
        source_snapshot.write_text(tex.read_text())
        event = self.append("compile_provenance", tex=str(tex), tex_sha256=provenance.sha(tex),
                            source_snapshot=str(source_snapshot), source_snapshot_sha256=provenance.sha(source_snapshot),
                            provenance_snapshot=str(snapshot / "figure_provenance.json"), provenance_sha256=self.manifest_sha)
        pdf = tex.with_suffix(".pdf")
        start = self.append("compile_start", tex=str(tex), pdf=str(pdf), tex_sha256=provenance.sha(tex))
        self.make_pdf(pdf, self.visible_text("LABELLED COMPILED MANUSCRIPT FIXTURE: " + name),
                      images=[self.root / item["image_path"] for item in self.manifest["figures"]])
        end = self.append("compile_end", pdf=str(pdf), exists=True, sha256=provenance.sha(pdf))
        self.compiles.append({"tex": tex, "pdf": pdf, "snapshot": source_snapshot,
                              "event": event, "start": start, "end": end})

    def reanchor(self):
        self.run["artifacts"] = {path.relative_to(self.root).as_posix(): provenance.sha(path)
                                 for path in self.root.rglob("*") if path.is_file()
                                 and "execution" not in path.relative_to(self.root).parts}

    def audit(self):
        return AUDIT.audit(self.root, self.run, self.trace)

    def invalid(self, text):
        summary, errors = self.audit()
        self.assertFalse(summary["valid"], summary)
        self.assertTrue(any(text in error for error in errors), errors)

    def rewrite_effective(self, index, mutate):
        record = self.calls[index]
        value = json.loads(record["effective"].read_text())
        mutate(value)
        record["effective"].write_text(json.dumps(value, indent=2))
        record["event"]["effective_sha256"] = provenance.sha(record["effective"])
        record["parsed_file"].write_text(json.dumps(value["parsed_response"], indent=2))
        record["call_end"]["sha256"] = provenance.sha(record["parsed_file"])

    def test_complete_section_content_format_raw_and_compile_chains_pass(self):
        summary, errors = self.audit()
        self.assertEqual(errors, [])
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["writer_requests_checked"], 3)
        self.assertEqual(summary["manuscript_results_checked"], 3)
        self.assertEqual(len(summary["compiled_manuscripts"]), 3)
        self.assertTrue(summary["final_pdf_visible_references"])
        self.assertTrue(summary["final_pdf_selected_images_verified"])
        self.assertIn("filecontents", self.calls[1]["directory"].joinpath("response.txt").read_text())
        self.assertNotIn("filecontents", AUDIT.result_tex(json.loads(self.calls[1]["effective"].read_text())))

    def test_legacy_policy_bypasses_without_reading_nonexistent_files(self):
        summary, errors = AUDIT.audit(self.root / "absent", {"status": "completed"}, [])
        self.assertFalse(summary["enabled"])
        self.assertFalse(summary["checks_performed"])
        self.assertEqual(errors, [])

    def test_historical_full_run_is_backward_auditable_without_new_claims(self):
        historical = ROOT / "validation/installed-r-tikz-e2e/run.json"
        if not historical.exists():
            self.skipTest("Historical run is an optional development artifact")
        run = json.loads(historical.read_text())
        self.assertNotEqual(run.get("manuscript_provenance"), 1)
        summary, errors = AUDIT.audit(historical.parent, run, [])
        self.assertEqual(errors, [])
        self.assertFalse(summary["enabled"])

    def test_actual_original_source_hash_drift_is_rejected(self):
        original = self.root / self.manifest["figures"][0]["original_directory"] / "source.R"
        original.write_text(original.read_text() + "\n# altered renderer source")
        self.invalid("renderer artifact")

    def test_workspace_source_hash_drift_is_rejected(self):
        copy_path = self.root / "content_refinement_workdir" / self.manifest["figures"][0]["source"]
        copy_path.write_text("different source")
        self.invalid("provenance mismatch")

    def test_selected_render_context_cannot_point_to_another_backend(self):
        next(event for event in self.trace if event["event"] == "render_end")["backend"] = "tikz"
        self.invalid("actual render")

    def test_missing_exact_worker_context_is_rejected_even_with_rehashed_prompt(self):
        record = self.calls[0]
        prompt = record["directory"] / "prompt.txt"
        prompt.write_text("A generic instruction about R and TikZ; no actual sources.")
        checksum = provenance.sha(prompt)
        record["start"]["prompt_sha256"] = checksum
        request_path = record["directory"] / "request.json"
        request = json.loads(request_path.read_text())
        request["prompt_sha256"] = checksum
        request_path.write_text(json.dumps(request))
        self.invalid("exact manifest/source snapshots")

    def test_missing_request_provenance_fields_is_rejected(self):
        self.calls[1]["start"].pop("figure_provenance_files")
        self.invalid("exact selected-source context")

    def test_upstream_raw_channel_must_match_actual_worker_response(self):
        record = self.calls[1]
        original = json.loads(record["upstream"].read_text())
        original["raw_response"] = "The original worker never wrote this."
        record["upstream"].write_text(json.dumps(original))
        record["event"]["original_sha256"] = provenance.sha(record["upstream"])
        self.invalid("actual worker response")

    def test_rehashed_raw_response_cannot_replace_native_worker_output(self):
        record = self.calls[0]
        response = record["directory"] / "response.txt"
        raw = response.read_text() + "\nEdited after execution"
        response.write_text(raw)
        record["end"]["response_sha256"] = provenance.sha(response)
        original = json.loads(record["upstream"].read_text())
        original["raw_response"] = raw
        record["upstream"].write_text(json.dumps(original))
        record["event"]["original_sha256"] = provenance.sha(record["upstream"])
        self.invalid("native worker message")

    def test_unrecorded_effective_latex_rewrite_is_rejected_after_rehash(self):
        self.rewrite_effective(0, lambda value: value.update(parsed_response="rewritten paper"))
        self.invalid("transformation differs")

    def test_format_editor_raw_channel_is_audited_not_only_parsed_channel(self):
        self.rewrite_effective(2, lambda value: value.update(raw_response="unrecorded formatting rewrite"))
        self.invalid("transformation differs")

    def test_successful_writer_cannot_omit_transformation_event(self):
        event = self.calls[2]["event"]
        self.trace.remove(event)
        self.invalid("no raw/effective manuscript transformation")

    def test_dropped_final_references_are_rejected_even_when_manifest_rehashed(self):
        path = self.root / "content_refinement_workdir/final_refined_paper.tex"
        path.write_text(r"\documentclass{article}\begin{document}Lost references.\end{document}")
        self.reanchor()
        self.invalid("missing, changed")

    def test_alternative_recipe_in_final_manuscript_is_rejected(self):
        path = self.root / "content_refinement_workdir/final_refined_paper.tex"
        path.write_text(path.read_text().replace(r"\begin{document}",
                        '\\begin{filecontents*}{other.R}\nlibrary(ggplot2)\np<-ggplot()\n\\end{filecontents*}\n\\begin{document}', 1))
        self.reanchor()
        self.invalid("alternative recipe")

    def test_compiler_source_snapshot_must_match_effective_handoff(self):
        snapshot = self.compiles[1]["snapshot"]
        snapshot.write_text(snapshot.read_text().replace("CONTENT", "CHANGED AFTER HANDOFF"))
        self.compiles[1]["event"]["source_snapshot_sha256"] = provenance.sha(snapshot)
        self.invalid("snapshot hash differs")

    def test_later_candidate_path_overwrite_does_not_destroy_recorded_compile_proof(self):
        self.compiles[0]["tex"].write_text("LABELLED LATER ATTEMPT OVERWROTE THIS PATH")
        self.reanchor()
        summary, errors = self.audit()
        self.assertTrue(summary["valid"], errors)
        self.assertEqual(len(summary["compiled_manuscripts"]), 3)

    def test_final_tex_and_pdf_must_be_from_one_compiled_source(self):
        final = self.root / "content_refinement_workdir/final_refined_paper.tex"
        final.write_text(self.compiles[0]["snapshot"].read_text())
        self.reanchor()
        self.invalid("one accepted compiled manuscript")

    def test_whole_paper_retry_can_use_new_sources_without_invalidating_old_snapshots(self):
        old_original = self.root / self.manifest["figures"][0]["original_directory"]
        new_original = self.root / "figure_sources/labelled-second-paper-attempt"
        shutil.copytree(old_original, new_original)
        (new_original / "source.R").write_text((new_original / "source.R").read_text() + "\n# SECOND LABELLED ATTEMPT")
        Image.new("RGB", (80, 40), "blue").save(new_original / "preview.jpg")
        metadata = json.loads((new_original / "render.json").read_text())
        metadata["source_sha256"] = provenance.sha(new_original / "source.R")
        metadata["files_sha256"]["source.R"] = metadata["source_sha256"]
        metadata["preview_sha256"] = provenance.sha(new_original / "preview.jpg")
        (new_original / "render.json").write_text(json.dumps(metadata, indent=2))
        render_fields = {"figure_id": self.fig, "backend": "ggplot2", "directory": str(new_original),
                         "source_sha256": metadata["source_sha256"]}
        self.append("render_start", **render_fields)
        self.append("render_end", **render_fields, source="source.R", pdf_sha256=metadata["pdf_sha256"],
                    preview_sha256=metadata["preview_sha256"])
        shutil.copyfile(new_original / "preview.jpg", self.root / f"figures/{self.fig}.jpg")
        self.save_trace()
        self.manifest = provenance.build_manifest(self.root)
        self.manifest_sha = provenance.sha(self.root / "figure_provenance.json")
        self.append("provenance_published", stage="SectionWritingAgent", sha256=self.manifest_sha)
        for name in AUDIT.WORKSPACES:
            provenance.publish_workspace(self.root, self.root / name)
        tex = r"\documentclass{article}\begin{document}LABELLED SECOND PAPER ATTEMPT.\end{document}"
        effective = self.add_manuscript("section-writer", "section", tex)
        self.add_compile("initial_draft", effective)
        (self.root / "content_refinement_workdir/final_refined_paper.tex").write_text(AUDIT.result_tex(effective))
        shutil.copyfile(self.compiles[-1]["pdf"], self.root / "final_paper.pdf")
        self.reanchor()
        summary, errors = self.audit()
        self.assertTrue(summary["valid"], errors)
        self.assertEqual(summary["writer_requests_checked"], 4)
        self.assertEqual(len(summary["compiled_manuscripts"]), 4)

    def test_printed_source_references_do_not_substitute_for_selected_embedded_image(self):
        final = self.root / "final_paper.pdf"
        final.unlink()
        self.make_pdf(final, self.visible_text("LABELLED PDF WITH REFERENCES BUT NO IMAGE"))
        self.compiles[-1]["end"]["sha256"] = provenance.sha(final)
        self.reanchor()
        self.invalid("does not embed the exact selected figure preview")

    def test_replacement_embedded_image_is_rejected_even_with_exact_printed_references(self):
        replacement = self.root / "labelled-wrong-preview.jpg"
        Image.new("RGB", (80, 40), "red").save(replacement)
        final = self.root / "final_paper.pdf"
        final.unlink()
        self.make_pdf(final, self.visible_text("LABELLED PDF WITH WRONG FIGURE"), images=[replacement])
        self.compiles[-1]["end"]["sha256"] = provenance.sha(final)
        self.reanchor()
        self.invalid("does not embed the exact selected figure preview")

    def test_final_pdf_must_visibly_reference_sources_not_just_tex(self):
        final = self.root / "final_paper.pdf"
        final.unlink()
        self.make_pdf(final, "LABELLED PDF WITH NO PROVENANCE TEXT")
        self.compiles[-1]["end"]["sha256"] = provenance.sha(final)
        self.reanchor()
        self.invalid("no visible figure-source provenance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
