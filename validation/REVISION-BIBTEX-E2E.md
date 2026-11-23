# Live content revision with verified BibTeX

The exact installed skill completed on 23 November 2026. All three content
revisions used the original `references.bib` and the baseline's `plain`
style. All three compiled with resolved citations and reached independent
review. The controller accepted two revisions and retained the second for
formatting. The final PDF contains five resolved references on page 5.

[Run manifest](revision-bibtex-e2e/run.json) ·
[Independent check results](revision-bibtex-e2e-checks.json) ·
[Final manuscript](revision-bibtex-e2e/final_paper.pdf) ·
[Reproducible source project](../dist/revision-bibtex-verified-manuscript.zip)

| Candidate | Resolved citations | Overall score | Controller decision |
|---|---:|---:|---|
| Initial draft | 64 | 2 | Baseline |
| Revision 1 | 5 | 3 | Accepted on score increase |
| Revision 2 | 5 | 3 | Accepted with one criterion improved and none declined |
| Revision 3 | 6 | 3 | Rejected with one criterion declined and none improved |

The citation count fell during reviewed content revision as the editor shortened
the draft. The single formatting pass changed three figure or table placement
options and preserved revision 2's five citations. The compiled bibliography
is byte-identical before and after formatting. Inspection of the six-page PDF
confirmed the reference list and both figures are visible.
[Content worklog](revision-bibtex-e2e/content_refinement_workdir/content_refinement_worklog.json) ·
[Bibliography audit](revision-bibtex-e2e-bibliography.json)

The frozen 61-file bundle at launch and completion was
`061e40d7c0716ae965437d9962c4242603e04d4def92aa99e1e20ca7b26c5815`.
The run used the same four-runtime profile and fixture as the formatting
validation, including the parallel R/ggplot2 and TikZ branches. It took about
29 minutes, with 60 separate successful worker invocations. The audit verifies
all four reviewer ensembles, 36 aggregate values and 121 artifact checksums.
Literature and plotting overlapped for 458.7 seconds. All six successful figure
renders replayed to identical previews without model calls.
[Freeze receipt](revision-bibtex-freeze.json) ·
[Trace audit](revision-bibtex-e2e/execution/audit.json) ·
[Figure replay](revision-bibtex-e2e-replay/replay.json)

The three live editors kept the BibTeX declarations in their raw outputs. The
fallback was tested separately with the three recorded inline-reference
revisions from the previous formatting validation. Replacing their trailing
lists with the verified declarations preserved their in-text citations, and
real BibTeX compilation resolved 3, 3 and 4 references. The test suite passed
all 330 tests. The final manuscript archive also rebuilt from a clean directory
using the exact TeX and figure files, with all five references resolved.
[Test receipt](revision-bibtex-tests.log) ·
[Source project rebuild](revision-bibtex-source-project.json)
