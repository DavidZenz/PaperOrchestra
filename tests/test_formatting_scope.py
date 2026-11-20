"""Regression checks for the formatting boundary and upstream fallback."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "paper-orchestra/vendor"))
import orchestra_runtime
from orchestra_formatting import FormattingScopeError, validate_formatting
from methods.agents import content_refinement_agent as refinement
from orchestra_runtime import Runtime, configure, instrument

TEX = r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
For the observed inputs, $b=3$ \cite{First,Second}.
\begin{figure}[htbp]
    \includegraphics[width=\linewidth]{plot.pdf}
    \caption{The measured result.}
\end{figure}
\begin{verbatim}
\begin{figure}[htbp]
\end{verbatim}
\bibliographystyle{plain}
\bibliography{references}
\end{document}"""
LAYOUT_ONLY = TEX.replace(r"\begin{figure}[htbp]", r"\begin{figure}[t]", 1).replace(
    r"width=\linewidth", r"width=0.85\linewidth")
ARCHIVED = ROOT / "validation/reference-fix-e2e-complete/content_refinement_workdir"


class FormattingScopeTests(unittest.TestCase):
    def test_layout_options_are_allowed_but_scientific_source_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / "format_candidate_v0.tex").write_text(TEX)
            candidate = work / "formatted_candidate_v1.tex"
            candidate.write_text(LAYOUT_ONLY)
            validate_formatting(work, candidate)
            for changed in [
                LAYOUT_ONLY.replace("First,Second", "First"),
                LAYOUT_ONLY.replace(r"\cite{First,Second}", r"\nocite{First,Second}"),
                LAYOUT_ONLY.replace("$b=3$", "$b=4$"),
                LAYOUT_ONLY.replace("measured result", "held-out result"),
                LAYOUT_ONLY.replace("{plot.pdf}", "{other.pdf}"),
                LAYOUT_ONLY.replace("0.85", "0"),
                LAYOUT_ONLY.replace(r"\bibliography{references}", r"\bibliography{other}"),
                # Looks like a float edit, but the line is part of a code listing.
                LAYOUT_ONLY.replace(r"\begin{figure}[htbp]", r"\begin{figure}[t]"),
            ]:
                with self.subTest(change=changed):
                    candidate.write_text(changed)
                    with self.assertRaises(FormattingScopeError):
                        validate_formatting(work, candidate)

    @unittest.skipUnless((ARCHIVED / "formatted_candidate_v1.tex").is_file(),
                         "Recorded reference regression is absent")
    def test_recorded_42_to_18_formatter_output_is_rejected(self):
        def citations(path):
            return {key for group in re.findall(r"\\cite\{([^}]+)\}", path.read_text())
                    for key in group.split(",")}
        old = ARCHIVED / "formatted_candidate_v1.tex"
        baseline = ARCHIVED / "format_candidate_v0.tex"
        self.assertEqual((len(citations(baseline)), len(citations(old))), (42, 18))
        with self.assertRaises(FormattingScopeError):
            validate_formatting(ARCHIVED, old)

    def test_original_controller_keeps_input_on_scope_failure_and_accepts_layout(self):
        for candidate, accepted in [(TEX.replace("First,Second", "First"), False),
                                    (LAYOUT_ONLY, True)]:
            with self.subTest(accepted=accepted), ExitStack() as stack:
                from methods.agents.literature_review_agent import HybridLiteratureAgent
                from methods.agents.outline_agent import OutlineAgent
                from methods.agents.plotting_agent import PlottingAgent
                from methods.agents.section_writing_agent import SectionWritingAgent
                import requests

                work = Path(stack.enter_context(tempfile.TemporaryDirectory()))
                stack.callback(configure, orchestra_runtime._runtime)
                prompts = []

                def executor(command, prompt, directory):
                    prompts.append(prompt)
                    if "Analyze the provided page images" in prompt:
                        return '{"figure_and_tables": {}, "other_issues": ["Adjust float placement"]}'
                    return "```latex\n" + candidate + "\n```"

                configure(Runtime(work / "execution", executor=executor,
                                  formatting_scope_required=True))
                for cls in (OutlineAgent, PlottingAgent, HybridLiteratureAgent, SectionWritingAgent,
                            refinement.ContentRefinementAgent):
                    stack.enter_context(patch.object(cls, "run", cls.run))
                stack.enter_context(patch.object(requests, "get", requests.get))
                stack.enter_context(patch.object(refinement, "pdf_to_grid_images", return_value=[]))
                stack.enter_context(redirect_stdout(io.StringIO()))

                compiles = []

                def compiler(cwd, pdf, basename, timeout):
                    compiles.append(basename)
                    Path(pdf).write_bytes(b"fixture: " + basename.encode())

                stack.enter_context(patch.object(refinement, "compile_latex", compiler))
                instrument(work)
                (work / "draft.tex").write_text(TEX)
                (work / "references.bib").write_text("@misc{First, title={First}}\n")
                (work / "guidelines.md").write_text("Use the supplied layout.")
                (work / "log.md").write_text("Finite fixture")
                (work / "citation_map.json").write_text("{}")
                agent = refinement.ContentRefinementAgent(
                    str(work / "log.md"), str(work / "citation_map.json"),
                    str(work / "guidelines.md"), work_dir=str(work), max_reflections=0)
                peer = stack.enter_context(patch.object(agent, "_get_peer_review", return_value=({}, 2)))
                final = Path(agent.run(str(work / "draft.tex")))
                self.assertEqual(peer.call_count, 1)
                self.assertEqual(len(prompts), 2)
                self.assertTrue(all("[FORMATTING SCOPE]" in prompt for prompt in prompts))
                basename = "formatted_candidate_v1" if accepted else "initial_draft"
                self.assertEqual(final.read_bytes(), (work / f"{basename}.pdf").read_bytes())
                self.assertEqual((work / "final_refined_paper.tex").read_text(),
                                 candidate if accepted else TEX)
                self.assertEqual(compiles, ["initial_draft", basename] if accepted else ["initial_draft"])
                self.assertEqual(agent.format_worklogs["v1"]["outcome"],
                                 "ACCEPTED_COMPILE_SUCCESS" if accepted else "REJECTED_COMPILE_FAILURE")
                events = [json.loads(line) for line in (work / "execution/trace.jsonl").read_text().split("\n") if line]
                self.assertEqual([e["valid"] for e in events if e["event"] == "formatting_scope"],
                                 [accepted])
