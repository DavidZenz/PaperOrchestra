# Formatting scope audit

The final formatting operation changed scientific prose and removed24 existing
approved citations (42 to 18). Its bibliography remains valid, but the operation
does not satisfy the user's intended formatting-only boundary. Previous evidence
for valid surviving references must not be interpreted as preservation of the
accepted paper's scientific content or citation coverage.

## Trace and cause

The recorded format-editor invocation is
`2b60448501eb4859b763e5c089a44fa2`, Claude Haiku5.5 at medium effort. Its input
`format_candidate_v0.tex` contains42 distinct citation keys; its raw response and
accepted `formatted_candidate_v1.tex` both contain18. The source-provenance
adapter did not remove citations. The underlying45-record `references.bib` is
byte-identical across literature, writeup and refinement workspaces. BibTeX
printed fewer entries because the formatter removed the corresponding uses.

The reviewer requested: “Trim the Related Work and Section4 prose to bring the
body within about700–1000words.” The copied upstream editor prompt prohibits
content/citation changes **unless explicitly allowed by the feedback**. The
upstream formatting-review prompt also requests condensation when over length.
This makes formatting and substantive editing responsibilities overlap. The
feedback did not expressly request deletion of24 citations.

The worker removed whole cited scientific-context passages, including visual
inference (Buja2009), forecasting correction/structural-change context
(Glahn1972/Maraun2016/Clements1996), and cross-validation/predictive-sample-reuse
context (Stone1974/Geisser1975/Arlot2010). This was more than typography or float
placement. No new citation keys were introduced.

Upstream accepts formatting on PDF compilation alone, with no scientific review
afterward. Our new gate additionally checked nonempty/approved/resolved/visible
references, but never compared scientific content or citation coverage with the
formatting input. Therefore the18-reference result passed. Abstract-based checks
of surviving claims likewise did not test whether scientific material was lost.

## Fix and recovery

Formatting feedback now treats scientific edits as unresolved issues for the
content stage. The driver compares the formatter's LaTeX against the last
accepted source and rejects edits outside the supported float layout options.
The original rejection branch retains the accepted TeX and PDF. Completion and
the trace auditor also check the final source. The new behavior is documented
as R030 and A007.

All 326 tests passed. The regression check rejected the recorded candidate,
and the controller tests confirmed fallback on citation loss and acceptance of
an allowed layout edit. The bundle hashes match the installed skill.

The recovered source project contains the pre-formatting PDF and TeX and the
exact R and TikZ sources. A clean rebuild reproduced the manuscript text and
all 42 resolved references. The references are on pages 8–10. The original
length feedback remains unresolved on this draft. The recovery reused the
earlier run and made zero model calls.

[Recovered source project](../dist/formatting-recovered-manuscript.zip) ·
[Rebuild evidence](formatting-recovery.json) ·
[Installed bundle](formatting-scope-freeze.json) ·
[Exact removed citation keys](formatting-scope-audit.json)
