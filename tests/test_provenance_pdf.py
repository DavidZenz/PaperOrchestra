"""Real TeX/PDF reference round-trip; no model or generated measurements."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper-orchestra/vendor"))
from orchestra_provenance import normalize_latex


@unittest.skipUnless(shutil.which("pdflatex"), "pdfLaTeX is required for the PDF round-trip")
class ProvenancePDFTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("bibtex"), "BibTeX is required for the bibliography round-trip")
    def test_upstream_compiler_renders_reference_list_after_provenance_normalization(self):
        import pymupdf
        from utils.pdf_utils import compile_latex
        from methods.agents.literature_review_agent import HybridLiteratureAgent, PaperData
        paper = PaperData(citation_key="Fixture2020", title="Bibliography Conformance Fixture",
                          authors=["Fixture Author"], venue="Fixture Venue", year=2020,
                          abstract="Labelled test input, not real literature.", citation_count=0,
                          found_in_section="Introduction", reason="test")
        bibliography = HybridLiteratureAgent._generate_bibtex(None, [paper])
        manifest = {"figures": [{
            "figure_id": "fixture", "image_path": "figures/fixture.jpg", "backend": "ggplot2",
            "source": "figure_code/fixture/source.R", "source_sha256": "a" * 64, "files": {}}]}
        tex, _ = normalize_latex(
            r"\documentclass{article}\begin{document}Fixture~\cite{Fixture2020}."
            r"\bibliographystyle{plain}\bibliography{references}\end{document}", manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "paper.tex").write_text(tex)
            (path / "references.bib").write_text(bibliography)
            compile_latex(str(path), str(path / "compiled.pdf"), "paper")
            self.assertTrue((path / "compiled.pdf").is_file())
            self.assertIn(r"\bibitem{Fixture2020}", (path / "paper.bbl").read_text())
            with pymupdf.open(path / "compiled.pdf") as document:
                visible = " ".join(page.get_text() for page in document)
            self.assertIn("References", visible)
            # plain.bst applies sentence case to article/proceedings titles.
            self.assertIn("bibliography conformance fixture", visible.lower())
            self.assertNotIn("Citation `Fixture2020'", (path / "paper.log").read_text())

    def test_default_ot1_pdf_retains_copyable_exact_source_and_wrapper_paths(self):
        import pymupdf
        source = "figure_code/fig_intercept_error/source.R"
        wrapper = "figure_code/fig_intercept_error/worker.R"
        source_hash = hashlib.sha256(b"explicit test source").hexdigest()
        wrapper_hash = hashlib.sha256(b"explicit test wrapper").hexdigest()
        manifest = {"schema_version":1, "figures":[{
            "figure_id":"fig_intercept_error", "image_path":"figures/fig_intercept_error.jpg",
            "backend":"ggplot2", "source":source, "source_sha256":source_hash,
            "files":{source:source_hash, wrapper:wrapper_hash,
                     "figure_code/fig_intercept_error/render.json":"0" * 64}}]}
        tex, _ = normalize_latex(r"\documentclass{article}\begin{document}Measured results.\end{document}", manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "paper.tex").write_text(tex)
            result = subprocess.run(["pdflatex", "-no-shell-escape", "-interaction=nonstopmode",
                                     "-halt-on-error", "paper.tex"], cwd=path,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout[-4000:])
            with pymupdf.open(path / "paper.pdf") as document:
                visible = "".join("".join(page.get_text().split()) for page in document)
            for expected in [source, wrapper, source_hash, wrapper_hash, "fig_intercept_error.jpg"]:
                self.assertIn(expected, visible)


if __name__ == "__main__":
    unittest.main()
