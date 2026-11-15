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
