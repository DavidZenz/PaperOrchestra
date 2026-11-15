"""Exact-source policy must not rewrite unrelated scientific/template material."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper-orchestra/vendor"))
from orchestra_provenance import normalize_latex, ProvenanceError, BEGIN


class ProvenanceScopeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"schema_version":1, "figures":[{
            "figure_id":"fig_result", "image_path":"figures/fig_result.jpg",
            "backend":"ggplot2", "source":"figure_code/fig_result/source.R",
            "source_sha256":"1" * 64, "files":{}}]}

    def test_template_tikz_setup_and_prose_function_names_are_preserved(self):
        preamble = (r"\documentclass{article}\usepackage{tikz}\usetikzlibrary{arrows.meta}"
                    r"\newcommand{\publisherlogo}{\begin{tikzpicture}\draw(0,0)--(1,1);\end{tikzpicture}}")
        discussion = r"The retained source calls \texttt{ggplot()} and \texttt{geom_point()} on measured data."
        tex = preamble + r"\begin{document}" + discussion + r"\end{document}"
        actual, removed = normalize_latex(tex, self.manifest)
        self.assertEqual(removed, [])
        self.assertIn(preamble, actual)
        self.assertIn(discussion, actual)
        self.assertIn(BEGIN, actual)
        self.assertEqual(normalize_latex(actual, self.manifest)[0], actual)

    def test_only_renderer_recipes_are_removed_not_data_scripts_styles_or_comments(self):
        data = "\\begin{filecontents*}{analysis.R}\nlibrary(ggplot2)\nmean(c(1,2,3))\n\\end{filecontents*}"
        style = (r"\begin{filecontents*}{venue.sty}\usetikzlibrary{arrows.meta}"
                 r"\newcommand{\logo}{\begin{tikzpicture}\end{tikzpicture}}\end{filecontents*}")
        recipe = "\\begin{filecontents*}{replacement.R}\np <- ggplot(data, aes(x,y)) + geom_point()\n\\end{filecontents*}"
        comment = "% Example token \\begin{tikzpicture} is not executed.\n"
        tex = r"\documentclass{article}" + data + style + recipe + r"\begin{document}" + comment + "Results." + r"\end{document}"
        actual, removed = normalize_latex(tex, self.manifest)
        self.assertEqual(removed, ["replacement.R"])
        self.assertIn(data, actual)
        self.assertIn(style, actual)
        self.assertIn(comment, actual)
        self.assertNotIn(recipe, actual)

    def test_active_inline_tikz_remains_rejected(self):
        for graphic in [r"\begin{tikzpicture}\draw(0,0)--(1,1);\end{tikzpicture}",
                        r"\tikz[baseline]\node{replacement};"]:
            with self.subTest(graphic=graphic), self.assertRaises(ProvenanceError):
                normalize_latex(r"\documentclass{article}\begin{document}" + graphic + r"\end{document}", self.manifest)

    def test_commented_document_marker_does_not_hide_an_active_inline_picture(self):
        tex = ("\\documentclass{article}\\begin{document}\n"
               "\\begin{tikzpicture}\\draw(0,0)--(1,1);\\end{tikzpicture}\n"
               "% A commented \\begin{document} is not the document start.\n"
               "\\end{document}")
        with self.assertRaises(ProvenanceError):
            normalize_latex(tex, self.manifest)


if __name__ == "__main__":
    unittest.main()
