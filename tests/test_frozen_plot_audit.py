"""Frozen-build and plotted-handoff audits using labelled agent trace fixtures.

The source/PDF/JPEG files are rendered by real local R; no model is invoked.
"""
import json
from pathlib import Path
import shutil
import unittest

import tests.test_trace_audit as fixtures
from tests.test_code_renderers import RSCRIPT, R_FIXTURE
import orchestra_visuals as visuals
from orchestra_runtime import figure_context


@unittest.skipUnless(Path(RSCRIPT).is_file(), "real R/ggplot2 engine required")
class FrozenPlotAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TraceAuditTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.figure_id = "Figure 1"
        self.directory = self.root / "figure_sources" / "labelled-r-render-fixture"
        token = figure_context.set(self.figure_id)
        try:
            self.metadata = visuals.write_sources(self.directory, R_FIXTURE.strip(), "ggplot2", "4:3")
        finally:
            figure_context.reset(token)
        command = visuals.render_saved(self.directory, rscript=RSCRIPT)
        self.metadata.update(status="rendered", command=command,
                             pdf_sha256=fixtures.digest(self.directory / "figure.pdf"),
                             preview_sha256=fixtures.digest(self.directory / "preview.jpg"))
        (self.directory / "render.json").write_text(json.dumps(self.metadata))
        for relative in ["figures/figure_1.jpg", "latex_writeup/figures/figure_1.jpg"]:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.directory / "preview.jpg", path)
            self.fixture.hashes[relative] = fixtures.digest(path)
        outline = json.dumps({"plotting_plan": [{"figure_id": self.figure_id, "plot_type": "plot"}]})
        self.fixture.write_artifact("outline.json", outline)
        self.fixture.write_artifact("literature_agent_output/outline_v1.json", outline)
        self.fixture.write_artifact("plotting_results.json", json.dumps([
            {"figure_id": self.figure_id, "task_name": "plot", "image_path": "figures/figure_1.jpg", "caption": "Fixture caption"}]))
        for file in self.directory.iterdir():
            if file.is_file():
                self.fixture.hashes[file.relative_to(self.root).as_posix()] = fixtures.digest(file)
        # Anchor metadata and every executable renderer input to the completed
        # run manifest, independently of mutable hashes inside render.json.
        for name in ["render.json", *self.metadata["files_sha256"]]:
            file = self.directory / name
            self.fixture.hashes[file.relative_to(self.root).as_posix()] = fixtures.digest(file)

        # Put a source-generating worker and its real render inside a plotting
        # stage that overlaps the still-active literature stage.
        old_trace = self.fixture.trace
        self.fixture.trace = []
        self.fixture.append("stage_start", stage="PlottingAgent", span="plot-stage", inputs=dict(self.fixture.hashes))
        self.fixture.append("figure_start", figure_id=self.figure_id, plan={"figure_id": self.figure_id})
        self.worker = self.fixture.add_agent("ggplot2-visualizer")
        self.replace_worker_response(R_FIXTURE)
        worker_start = next(e for e in self.fixture.trace if e["event"] == "agent_start" and e["invocation"] == self.worker)
        worker_start["figure_id"] = self.figure_id
        request_path = self.fixture.agent_dirs[self.worker] / "request.json"
        request = json.loads(request_path.read_text())
        request["figure_id"] = self.figure_id
        request_path.write_text(json.dumps(request))
        self.fixture.append("render_start", backend="ggplot2", figure_id=self.figure_id,
                            directory=str(self.directory), source_sha256=self.metadata["source_sha256"])
        self.fixture.append("render_end", backend="ggplot2", figure_id=self.figure_id,
                            directory=str(self.directory), source="source.R",
                            source_sha256=self.metadata["source_sha256"],
                            pdf_sha256=self.metadata["pdf_sha256"], preview_sha256=self.metadata["preview_sha256"])
        self.fixture.append("figure_end", figure_id=self.figure_id, task_name="plot",
                            preview_sha256=self.metadata["preview_sha256"], caption="Fixture caption")
        self.fixture.append("stage_end", stage="PlottingAgent", span="plot-stage", outputs=dict(self.fixture.hashes))
        plot_trace = self.fixture.trace
        lit_end = next(i for i, e in enumerate(old_trace) if e["event"] == "stage_end" and e.get("stage") == "HybridLiteratureAgent")
        self.fixture.trace = old_trace[:lit_end] + plot_trace + old_trace[lit_end:]
        for e in self.fixture.trace:
            if e["event"] == "stage_start" and e["stage"] == "SectionWritingAgent":
                e["inputs"] = dict(self.fixture.hashes)
        self.fixture.run.update(plotting=True, plot_backend="ggplot2", diagram_backend="tikz")
        self.fixture.run["artifacts"] = dict(self.fixture.hashes)

        self.installed = self.root / "labelled-installed-skill"
        self.installed.mkdir()
        (self.installed / "SKILL.md").write_text("LABELLED FROZEN SKILL FIXTURE")
        snapshot = self.root / "execution/skill_snapshot"
        shutil.copytree(self.installed, snapshot)
        state = fixtures.AUDIT.bundle_state(self.installed)
        self.fixture.run.update(skill_bundle=state, final_skill_bundle=state,
                                skill_unchanged=True, skill_path=str(self.installed))

    def replace_worker_response(self, source):
        directory = self.fixture.agent_dirs[self.worker]
        (directory / "response.txt").write_text(source)
        start = next(e for e in self.fixture.trace if e["event"] == "agent_start" and e["invocation"] == self.worker)
        end = next(e for e in self.fixture.trace if e["event"] == "agent_end" and e["invocation"] == self.worker)
        end["response_sha256"] = fixtures.digest(directory / "response.txt")
        parsed = self.root / "execution/parsed" / (start["call"] + ".json")
        parsed.write_text(json.dumps(source))
        next(e for e in self.fixture.trace if e["event"] == "llm_call_end" and e["call"] == start["call"])["sha256"] = fixtures.digest(parsed)

    def test_valid_frozen_source_backed_plot_fixture_passes(self):
        result = self.fixture.audit()
        self.assertTrue(result["evidence_valid"], result["errors"])
        self.assertTrue(result["parallel_plot_branch"])
        self.assertTrue(result["frozen_build"]["unchanged"])
        self.assertEqual(len(result["selected_figures"]), 1)
        self.assertTrue(result["selected_figures"][0]["code_generated_by_worker"])
        self.assertTrue(result["selected_figures"][0]["renderer_inputs_valid"])

    def test_missing_selected_source_is_rejected(self):
        (self.directory / "source.R").unlink()
        self.fixture.assert_invalid("code")

    def test_tampered_renderer_wrapper_is_rejected(self):
        (self.directory / "worker.R").write_text("tampered wrapper")
        self.fixture.assert_invalid("code")

    def test_coordinated_wrapper_and_metadata_tamper_cannot_replace_manifest_anchors(self):
        wrapper = self.directory / "worker.R"
        wrapper.write_text("# Coordinated fixture tamper\n" + wrapper.read_text())
        path = self.directory / "render.json"
        metadata = json.loads(path.read_text())
        metadata["files_sha256"]["worker.R"] = fixtures.digest(wrapper)
        path.write_text(json.dumps(metadata))
        self.assertNotEqual(self.fixture.run["artifacts"][wrapper.relative_to(self.root).as_posix()], fixtures.digest(wrapper))
        self.assertNotEqual(self.fixture.run["artifacts"][path.relative_to(self.root).as_posix()], fixtures.digest(path))
        result = self.fixture.audit()
        self.assertFalse(result["evidence_valid"], result)
        self.assertFalse(result["selected_figures"][0]["renderer_inputs_valid"])

    def test_selected_source_not_generated_by_worker_is_rejected(self):
        self.replace_worker_response("# unrelated valid-looking source\np <- 42")
        self.fixture.assert_invalid("code")

    def test_serialized_literature_plot_branches_are_rejected(self):
        trace = self.fixture.trace
        begin = next(i for i, e in enumerate(trace) if e["event"] == "stage_start" and e.get("stage") == "PlottingAgent")
        end = next(i for i, e in enumerate(trace) if e["event"] == "stage_end" and e.get("stage") == "PlottingAgent")
        plot = trace[begin:end + 1]
        remaining = trace[:begin] + trace[end + 1:]
        after_lit = next(i for i, e in enumerate(remaining) if e["event"] == "stage_end" and e.get("stage") == "HybridLiteratureAgent") + 1
        self.fixture.trace = remaining[:after_lit] + plot + remaining[after_lit:]
        self.fixture.assert_invalid("concurrently")

    def test_tampered_source_snapshot_is_rejected(self):
        (self.root / "execution/skill_snapshot/SKILL.md").write_text("snapshot tampered")
        self.fixture.assert_invalid("snapshot")

    def test_changed_finish_bundle_is_rejected(self):
        (self.installed / "SKILL.md").write_text("changed at finish")
        self.fixture.run["final_skill_bundle"] = fixtures.AUDIT.bundle_state(self.installed)
        self.fixture.run["skill_unchanged"] = False
        self.fixture.assert_invalid("unchanged")

    def test_changed_figure_copy_sent_to_section_writer_is_rejected(self):
        (self.root / "latex_writeup/figures/figure_1.jpg").write_bytes(b"unrelated figure")
        self.fixture.assert_invalid("handoff")


if __name__ == "__main__":
    unittest.main(verbosity=2)
