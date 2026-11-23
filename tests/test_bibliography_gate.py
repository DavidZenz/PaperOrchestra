"""Bibliography readiness adaptation: real compilation, no model/network calls."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper-orchestra/vendor"))
from orchestra_bibliography import (
    BibliographyError, restore_revision_bibliography, validate_library, validate_manuscript,
)

ARCHIVED = Path(__file__).resolve().parents[1] / "validation/formatting-scope-e2e-final/content_refinement_workdir"


class RevisionBibliographyTests(unittest.TestCase):
    @unittest.skipUnless(ARCHIVED.is_dir(), "Archived live run is absent")
    def test_recorded_inline_regressions_keep_their_original_cite_commands(self):
        for path in sorted(ARCHIVED.glob("refined_paper_v*.tex")):
            with self.subTest(candidate=path.name):
                original = path.read_text()
                restored = restore_revision_bibliography(original, "plain")
                self.assertNotEqual(original, restored)
                self.assertEqual(original.split(r"\begin{thebibliography}")[0],
                                 restored.split(r"\bibliographystyle")[0])
                self.assertEqual(re.findall(r"\\cite[a-zA-Z*]*\{[^{}]+\}", original),
                                 re.findall(r"\\cite[a-zA-Z*]*\{[^{}]+\}", restored))
                self.assertIn(r"\bibliography{references}", restored)
                self.assertNotIn(r"\begin{thebibliography}", restored)
                self.assertEqual(restore_revision_bibliography(restored, "plain"), restored)


class LibraryTests(unittest.TestCase):
    def test_empty_library_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "references.bib").write_text("")
            (path / "citation_map.json").write_text("{}")
            with self.assertRaisesRegex(BibliographyError, "Empty bibliography"):
                validate_library(path)

    def test_nonempty_library_must_have_identical_keys_and_complete_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "references.bib").write_text("@misc{Fixture2020, title={Fixture}}")
            record = {"title": "Fixture", "abstract": "Labelled test abstract"}
            (path / "citation_map.json").write_text(json.dumps({"Other": record}))
            with self.assertRaisesRegex(BibliographyError, "keys differ"):
                validate_library(path)
            (path / "citation_map.json").write_text(json.dumps({"Fixture2020": record}))
            self.assertEqual(validate_library(path)["keys"], ["Fixture2020"])
            (path / "citation_map.json").write_text(json.dumps({"Fixture2020": {"title": "Fixture"}}))
            with self.assertRaisesRegex(BibliographyError, "Incomplete"):
                validate_library(path)


@unittest.skipUnless(shutil.which("pdflatex") and shutil.which("bibtex"), "TeX/BibTeX required")
class CompiledGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.mapping = {"Fixture2020": {"title": "Bibliography Conformance Fixture", "abstract": "Labelled fixture"}}
        (self.path / "citation_map.json").write_text(json.dumps(self.mapping))
        (self.path / "references.bib").write_text(
            "@article{Fixture2020, title={Bibliography Conformance Fixture}, author={Fixture Author}, journal={Test Venue}, year={2020}}")
        (self.path / "paper.tex").write_text(
            r"\documentclass{article}\begin{document}Fixture~\cite{Fixture2020}."
            r"\bibliographystyle{plain}\bibliography{references}\end{document}")
        from utils.pdf_utils import compile_latex
        compile_latex(str(self.path), str(self.path / "paper.pdf"), "paper")

    def check(self, name="paper"):
        return validate_manuscript(self.path, name, self.path / "citation_map.json")

    def test_real_bibtex_output_visible_and_resolved(self):
        report = self.check()
        self.assertEqual(report["cited_keys"], ["Fixture2020"])
        self.assertEqual(report["visible_title_keys"], ["Fixture2020"])

    def test_inline_revision_compiles_with_verified_metadata_instead(self):
        from utils.pdf_utils import compile_latex
        paper = self.path / "revision.tex"
        original = (r"\documentclass{article}\begin{document}New explanation \cite{Fixture2020}."
                    "\n" + r"\begin{thebibliography}{9}" + "\n"
                    + r"\bibitem{Fixture2020} Model-supplied title." + "\n"
                    + r"\end{thebibliography}" + "\n" + r"\end{document}")
        paper.write_text(restore_revision_bibliography(original, "plain"))
        compile_latex(str(self.path), str(paper.with_suffix(".pdf")), paper.stem)
        self.assertEqual(self.check("revision")["visible_title_keys"], ["Fixture2020"])
        self.assertNotIn("Model-supplied title", paper.read_text())

    def test_compiled_database_must_match_the_verified_library(self):
        verified = self.path / "literature"
        verified.mkdir()
        shutil.copyfile(self.path / "citation_map.json", verified / "citation_map.json")
        bibliography = self.path / "references.bib"
        shutil.copyfile(bibliography, verified / "references.bib")
        validate_manuscript(self.path, "paper", verified / "citation_map.json")
        bibliography.write_text(bibliography.read_text() + "\n% Different database bytes\n")
        with self.assertRaisesRegex(BibliographyError, "differs from the verified library"):
            validate_manuscript(self.path, "paper", verified / "citation_map.json")

    def test_deposited_reserved_characters_render_without_changing_citation_key(self):
        from orchestra_bibliography import escape_bibtex_fields
        from utils.pdf_utils import compile_latex
        self.mapping["Fixture2020"]["title"] = "A & B with 50% and item_1 #2"
        (self.path / "citation_map.json").write_text(json.dumps(self.mapping))
        bib = "@article{Fixture2020,\n  title={A & B with 50% and item_1 #2},\n  author={Fixture Author},\n  journal={Test Venue},\n  year={2020}\n}"
        escaped = escape_bibtex_fields(bib)
        self.assertEqual(escape_bibtex_fields(escaped), escaped)
        (self.path / "references.bib").write_text(escaped)
        compile_latex(str(self.path), str(self.path / "paper.pdf"), "paper")
        self.assertEqual(self.check()["visible_title_keys"], ["Fixture2020"])

    def test_empty_bbl_rejected_despite_pdf(self):
        (self.path / "paper.bbl").write_text("")
        with self.assertRaisesRegex(BibliographyError, "Empty or unresolved"):
            self.check()

    def test_unknown_citation_rejected(self):
        path = self.path / "paper.aux"
        path.write_text(path.read_text() + "\n" + r"\citation{Unapproved}")
        with self.assertRaisesRegex(BibliographyError, "Unapproved citation"):
            self.check()

    def test_unresolved_citation_and_bibtex_errors_rejected(self):
        path = self.path / "paper.aux"
        path.write_text(path.read_text().replace(r"\bibcite{Fixture2020}", r"\bibcite{Missing}"))
        with self.assertRaisesRegex(BibliographyError, "unresolved"):
            self.check()
        path.write_text(path.read_text().replace(r"\bibcite{Missing}", r"\bibcite{Fixture2020}"))
        (self.path / "paper.blg").write_text("(There was 1 error message)")
        with self.assertRaisesRegex(BibliographyError, "BibTeX reported"):
            self.check()

    def test_removed_bibliography_commands_rejected(self):
        path = self.path / "paper.aux"
        path.write_text(path.read_text().replace(r"\bibdata{references}", ""))
        with self.assertRaisesRegex(BibliographyError, "Missing bibliography"):
            self.check()

    def test_final_copy_uses_only_byte_identical_compiled_candidate(self):
        for suffix in [".tex", ".pdf"]:
            shutil.copyfile(self.path / ("paper" + suffix), self.path / ("final_refined_paper" + suffix))
        self.assertEqual(self.check("final_refined_paper")["compiled_candidate"], "paper")
        with (self.path / "final_refined_paper.tex").open("a") as stream:
            stream.write("\n% altered")
        with self.assertRaisesRegex(BibliographyError, "byte-identical"):
            self.check("final_refined_paper")


if __name__ == "__main__":
    unittest.main()
