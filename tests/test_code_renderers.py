"""Real local renderer tests with labelled model-response fixtures, no LLM calls."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "paper-orchestra"
sys.path.insert(0, str(SKILL / "vendor"))
from orchestra_runtime import Runtime, configure, figure_context
import orchestra_visuals as visuals
from methods.agents import plotting_agent as plotting
from utils import paper_banana_utils as banana

SPEC = importlib.util.spec_from_file_location("paper_orchestra_replay_test", SKILL / "scripts/replay_figures.py")
REPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY)

RSCRIPT = "/opt/homebrew/opt/r/bin/Rscript"
R_FIXTURE = '''# LABELLED RENDERER FIXTURE: no generated or simulated data.
library(ggplot2)
d <- data.frame(x=c(1,2,3), y=c(1,4,9))
p <- ggplot(d, aes(x=x,y=y)) + geom_point() + geom_line() +
  theme_minimal() + labs(title="Renderer fixture", x="Input", y="Measured value")
'''
TIKZ_FIXTURE = r'''% LABELLED RENDERER FIXTURE: no image model involved.
\documentclass[tikz,border=5pt]{standalone}
\usepackage{amsmath}
\begin{document}
\begin{tikzpicture}
\node[draw] (a) at (0,0) {Input};
\node[draw] (b) at (3,0) {Output};
\draw[->] (a) -- (b);
\end{tikzpicture}
\end{document}
'''


class CodeExtractionTests(unittest.TestCase):
    def test_r_upper_and_lowercase_fences_and_plain_code(self):
        for response in ["```r\np <- 1\n```", "```R\np <- 1\n```", " p <- 1 "]:
            with self.subTest(response=response):
                self.assertEqual(visuals.extract_code(response, "r"), "p <- 1")

    def test_tex_and_latex_fences(self):
        for label in ["tex", "latex"]:
            self.assertEqual(visuals.extract_code(f"```{label}\nsource\n```", "latex"), "source")

    def test_dimensions_preserve_ratio_and_positive_size(self):
        width, height = visuals.dimensions("16:9")
        self.assertAlmostEqual(width / height, 16 / 9)
        self.assertAlmostEqual(max(width, height), 6.4)
        for ratio in ["0:1", "1:-1"]:
            with self.subTest(ratio=ratio), self.assertRaises(ValueError):
                visuals.dimensions(ratio)


@unittest.skipUnless(Path(RSCRIPT).is_file() and shutil.which("pdflatex"), "real R/TikZ engines required")
class RendererTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []
        self.responses = []

        def executor(command, prompt, directory):
            request = json.loads((directory / "request.json").read_text())
            self.calls.append({"command": command, "prompt": prompt, "request": request, "directory": directory})
            if self.responses:
                return self.responses.pop(0)
            return R_FIXTURE if request["role"] == "ggplot2-visualizer" else TIKZ_FIXTURE

        self.runtime = Runtime(self.root / "run" / "execution", rscript=RSCRIPT, executor=executor,
                               render_timeout=30)
        configure(self.runtime)

    def events(self):
        return [json.loads(s) for s in (self.runtime.root / "trace.jsonl").read_text().split("\n") if s]

    def rendered_dirs(self):
        return sorted((self.runtime.root.parent / "figure_sources").glob("*/render.json"))

    def assert_rendered(self, value, backend):
        self.assertTrue(base64.b64decode(value).startswith(b"\xff\xd8"))
        metadata = [json.loads(p.read_text()) for p in self.rendered_dirs()]
        selected = next(m for m in metadata if m["backend"] == backend and m["status"] == "rendered")
        file = next(p for p in self.rendered_dirs() if json.loads(p.read_text()) == selected)
        self.assertTrue((file.parent / "figure.pdf").read_bytes().startswith(b"%PDF"))
        self.assertEqual(visuals.digest(file.parent / selected["source"]), selected["source_sha256"])
        self.assertEqual(visuals.digest(file.parent / "preview.jpg"), selected["preview_sha256"])
        return file.parent, selected

    def test_real_r_ggplot_render_retains_source_vector_pdf_preview_and_session(self):
        token = figure_context.set("R fixture figure")
        try:
            value = visuals.generate_figure_visuals("plot", "exact points (1,1),(2,4),(3,9)", aspect_ratio="4:3")
        finally:
            figure_context.reset(token)
        directory, meta = self.assert_rendered(value, "ggplot2")
        self.assertEqual((directory / "source.R").read_text(), R_FIXTURE.strip())
        self.assertTrue((directory / "worker.R").is_file())
        self.assertIn("ggplot2", (directory / "sessionInfo.txt").read_text())
        self.assertEqual(meta["figure_id"], "R fixture figure")
        self.assertEqual(meta["aspect_ratio"], "4:3")
        self.assertEqual(self.calls[0]["request"]["role"], "ggplot2-visualizer")
        self.assertEqual(self.calls[0]["request"]["figure_id"], "R fixture figure")
        self.assertIn("Use R with ggplot2", self.calls[0]["prompt"])
        self.assertIn("exact points (1,1),(2,4),(3,9)", self.calls[0]["prompt"])

    def test_real_tikz_render_retains_editable_source_and_vector_pdf(self):
        token = figure_context.set("TikZ fixture figure")
        try:
            value = visuals.generate_figure_visuals("diagram", "Input node points to Output node")
        finally:
            figure_context.reset(token)
        directory, meta = self.assert_rendered(value, "tikz")
        self.assertEqual((directory / "source.tex").read_text(), TIKZ_FIXTURE.strip())
        self.assertIn("--", (directory / "source.tex").read_text())
        self.assertIn("-no-shell-escape", meta["command"])
        self.assertEqual(self.calls[0]["request"]["role"], "tikz-visualizer")
        self.assertIn("complete standalone LaTeX/TikZ document", self.calls[0]["prompt"])

    def test_failed_r_render_returns_upstream_none_and_keeps_failed_source(self):
        self.responses = ['stop("LABELLED R FIXTURE FAILURE")']
        value = visuals.generate_figure_visuals("plot", "fixture error")
        self.assertIsNone(value)
        file = self.rendered_dirs()[0]
        meta = json.loads(file.read_text())
        self.assertEqual(meta["status"], "failed")
        self.assertIn("LABELLED R FIXTURE FAILURE", (file.parent / "source.R").read_text())
        self.assertIn("LABELLED R FIXTURE FAILURE", (file.parent / "render.log").read_text())
        self.assertEqual(sum(e["event"] == "render_error" for e in self.events()), 1)

    def test_failed_tikz_render_returns_upstream_none(self):
        self.responses = [r"\documentclass{standalone}\begin{document}\undefinedFixtureCommand\end{document}"]
        self.assertIsNone(visuals.generate_figure_visuals("diagram", "fixture error"))
        self.assertEqual(json.loads(self.rendered_dirs()[0].read_text())["status"], "failed")

    def test_non_tikz_article_or_commented_picture_cannot_masquerade_as_diagram(self):
        cases = [
            (r"\documentclass{article}" + "\n% " + TIKZ_FIXTURE.replace("\n", "\n% ")
             + "\n" + r"\begin{document}Text-only article.\end{document}", "standalone"),
            (r"\documentclass{standalone}" + "\n% " + r"\begin{tikzpicture}\node{Comment only};\end{tikzpicture}"
             + "\n" + r"\begin{document}Text only.\end{document}", "editable TikZ picture"),
        ]
        for index, (code, message) in enumerate(cases):
            with self.subTest(index=index):
                directory = self.root / f"non-tikz-{index}"
                visuals.write_sources(directory, code, "tikz", "4:3")
                with patch.object(visuals.subprocess, "run", side_effect=AssertionError("Reject source before compiling")):
                    with self.assertRaisesRegex(ValueError, message):
                        visuals.render_saved(directory)

    def test_upstream_critic_receives_none_can_repair_and_selected_source_matches_final_image(self):
        self.responses = ['stop("LABELLED INITIAL FAILURE")', R_FIXTURE]
        materials = self.root / "materials"
        materials.mkdir()
        (materials / "experimental_log.md").write_text("Measured values: 1, 4, 9.")
        plan = {"figure_id": "repair fixture", "title": "Measurements", "plot_type": "plot",
                "objective": "compare points", "data_source": "experimental_log.md"}
        critic = Mock(side_effect=[("simpler corrected description", "Please repair"),
                                   ("same", "No changes needed.")])
        caption = Mock(return_value="Labelled fixture caption")
        # Restore every installed alias and hook, so other controller tests stay isolated.
        with ExitStack() as stack:
            stack.enter_context(patch.object(visuals, "_original_visualizer", None))
            for module, name in [(banana, "generate_figure_visuals"),
                                 (plotting, "generate_figure_visuals"),
                                 (plotting, "process_single_figure")]:
                stack.enter_context(patch.object(module, name, getattr(module, name)))
            for name, value in [("retrieve_few_shot_examples", []),
                                ("predict_figure_content", "initial description"),
                                ("style_figure_content", "styled description")]:
                stack.enter_context(patch.object(plotting, name, return_value=value))
            stack.enter_context(patch.object(plotting, "critique_and_revise_figure", critic))
            stack.enter_context(patch.object(plotting, "generate_figure_caption", caption))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            visuals.install()
            result = plotting.process_single_figure(plan, str(materials), max_critic_rounds=3)
        self.assertIsNone(critic.call_args_list[0].kwargs["base64_image"])
        self.assertTrue(critic.call_args_list[1].kwargs["base64_image"])
        self.assertEqual(result["description"], "simpler corrected description")
        self.assertEqual(result["caption"], "Labelled fixture caption")
        self.assertEqual(len(self.calls), 2)
        statuses = sorted(json.loads(p.read_text())["status"] for p in self.rendered_dirs())
        self.assertEqual(statuses, ["failed", "rendered"])
        selected = next(e for e in self.events() if e["event"] == "figure_end")
        render_end = next(e for e in self.events() if e["event"] == "render_end")
        self.assertEqual(selected["preview_sha256"], render_end["preview_sha256"])
        self.assertEqual(selected["figure_id"], "repair fixture")
        self.assertEqual(render_end["figure_id"], "repair fixture")
        self.assertIsNone(figure_context.get())

    def test_two_workers_keep_distinct_roles_figure_context_and_invocation_directories(self):
        def work(task, label):
            token = figure_context.set(label)
            try:
                return visuals.generate_figure_visuals(task, label)
            finally:
                figure_context.reset(token)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(work, "plot", "R parallel fixture"),
                       pool.submit(work, "diagram", "TikZ parallel fixture")]
            self.assertTrue(all(f.result() for f in results))
        self.assertEqual({c["request"]["role"] for c in self.calls}, {"ggplot2-visualizer", "tikz-visualizer"})
        self.assertEqual({c["request"]["figure_id"] for c in self.calls}, {"R parallel fixture", "TikZ parallel fixture"})
        self.assertEqual(len({c["directory"] for c in self.calls}), 2)
        self.assertIsNone(figure_context.get())

    def test_replay_invokes_no_model_and_produces_identical_previews(self):
        visuals.generate_figure_visuals("plot", "fixture points")
        visuals.generate_figure_visuals("diagram", "fixture nodes")
        calls_before = len(self.calls)
        with patch("utils.gemini_utils.call_gemini_with_contents", side_effect=AssertionError("Replay must not call an LLM")), \
             patch.object(Runtime, "generate", side_effect=AssertionError("Replay must not dispatch an agent")):
            result = REPLAY.replay(self.runtime.root.parent, self.root / "replay", rscript=RSCRIPT)
        self.assertEqual(len(self.calls), calls_before)
        self.assertEqual(result["llm_calls"], 0)
        self.assertEqual(len(result["figures"]), 2)
        self.assertTrue(result["all_previews_identical"], result)

    def test_stochastic_r_preview_is_raster_of_native_pdf_and_replay_is_identical(self):
        self.responses = ['''# LABELLED STOCHASTIC RENDERER FIXTURE ONLY.
library(ggplot2)
d <- data.frame(x=rep(1,12), y=1:12)
p <- ggplot(d, aes(x=x,y=y)) + geom_jitter(width=0.4,height=0.2) + theme_minimal()
''']
        visuals.generate_figure_visuals("plot", "labelled jitter fixture")
        directory = self.rendered_dirs()[0].parent
        import pymupdf
        independently_rasterized = self.root / "independent-pdf-preview.jpg"
        with pymupdf.open(directory / "figure.pdf") as document:
            self.assertEqual(len(document), 1)
            pix = document[0].get_pixmap(matrix=pymupdf.Matrix(300 / 72, 300 / 72), alpha=False)
            pix.set_dpi(300, 300)
            pix.save(independently_rasterized)
        self.assertEqual(visuals.digest(independently_rasterized), visuals.digest(directory / "preview.jpg"))
        self.assertEqual((directory / "worker.R").read_text().count("ggsave("), 1)
        with patch.object(Runtime, "generate", side_effect=AssertionError("Replay must not call a model")):
            result = REPLAY.replay(self.runtime.root.parent, self.root / "jitter-replay", rscript=RSCRIPT)
        self.assertEqual(result["llm_calls"], 0)
        self.assertTrue(result["all_previews_identical"], result)
        self.assertEqual(len(self.calls), 1)

    def test_replay_rejects_retained_source_tampering(self):
        visuals.generate_figure_visuals("plot", "fixture points")
        directory = self.rendered_dirs()[0].parent
        (directory / "source.R").write_text(R_FIXTURE + "\n# tampered source\n")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            REPLAY.replay(self.runtime.root.parent, self.root / "replay", rscript=RSCRIPT)

    def test_replay_rejects_retained_r_wrapper_tampering_before_execution(self):
        visuals.generate_figure_visuals("plot", "fixture points")
        directory = self.rendered_dirs()[0].parent
        metadata = json.loads((directory / "render.json").read_text())
        self.assertIn("worker.R", metadata["files_sha256"])
        (directory / "worker.R").write_text('stop("TAMPERED WRAPPER MUST NOT EXECUTE")\n')
        with patch.object(visuals.subprocess, "run", side_effect=AssertionError("Hash check must precede process launch")):
            with self.assertRaisesRegex(ValueError, "input hash mismatch: worker.R"):
                REPLAY.replay(self.runtime.root.parent, self.root / "replay", rscript=RSCRIPT)

    def test_stale_outputs_cannot_hide_renderer_failure(self):
        directory = self.root / "stale"
        visuals.write_sources(directory, 'stop("expected fixture failure")', "ggplot2", "4:3")
        (directory / "figure.pdf").write_bytes(b"stale PDF")
        (directory / "preview.jpg").write_bytes(b"stale JPEG")
        with self.assertRaises(RuntimeError):
            visuals.render_saved(directory, rscript=RSCRIPT)
        self.assertFalse((directory / "figure.pdf").exists())
        self.assertFalse((directory / "preview.jpg").exists())

    def test_legacy_matplotlib_and_image_dispatch_remain_original_calls(self):
        self.runtime.plot_backend = "matplotlib"
        self.runtime.diagram_backend = "image"
        original = Mock(return_value="original-result")
        with patch.object(visuals, "_original_visualizer", original):
            self.assertEqual(visuals.generate_figure_visuals("plot", "plot description", "writer", "image-model", "4:3"), "original-result")
            self.assertEqual(visuals.generate_figure_visuals("diagram", "diagram description", "writer", "image-model", "16:9"), "original-result")
        self.assertEqual(original.call_args_list[0].args, ("plot", "plot description", "writer", "image-model", "4:3"))
        self.assertEqual(original.call_args_list[1].args, ("diagram", "diagram description", "writer", "image-model", "16:9"))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
