# Live formatting preservation validation

The exact installed skill completed on 20 November 2026. The live formatting
editor changed one figure's placement from `[htbp]` to `[tbp]`. That was the
only LaTeX difference. All **35 references** survived, with identical citation
groups and order in the compiled auxiliary records and a byte-identical BibTeX
bibliography. The final PDF shows the full reference list on pages 8–10.

[Run manifest](formatting-scope-e2e-final/run.json) ·
[Verification checks](formatting-scope-e2e-checks.json) ·
[Manuscript PDF](formatting-scope-e2e-final/final_paper.pdf) ·
[Reproducible source project](../dist/formatting-verified-manuscript.zip)

## Execution and checks

- The driver ran from the installed skill, using the 61-file bundle
  `005725dbf9d5192bbc6f4c3f39c6587a6bf11e038110f7d1298b7c20fb56427f`.
  Launch, final, installed and recorded snapshot hashes agree. The run used
  the finite teaching-note fixture, the 2026-11 research cutoff and the prior
  four-runtime profile with `--use-plotting`. It exited 0 after 21 minutes and
  49 seconds. [Freeze receipt](formatting-transport-freeze.json)
- There were 48 separate worker process launches and 47 successful independent
  sessions. One Antigravity discovery attempt reported model or effort drift.
  The original retry succeeded in a fresh session. Seventeen searches had
  native search evidence. The trace audit found no errors or warnings and
  all 110 manifest artifact hashes matched.
  [Execution audit](formatting-scope-e2e-final/execution/audit.json)
- Literature and plotting overlapped for 562.5 seconds. Six successful R/ggplot2
  and TikZ render attempts replayed to identical previews with zero model calls.
  The manuscript references the exact selected sources and embeds the matching
  figure images. [Replay](formatting-scope-e2e-replay/replay.json)
- The library contains 38 verified records. Thirty-five are cited and resolved
  before and after formatting. All 35 titles are visible in the final PDF.
  The extracted source project rebuilt successfully with strict pdfLaTeX and
  BibTeX. [Bibliography audit](formatting-scope-e2e-bibliography.json) ·
  [Rebuild receipt](formatting-scope-e2e-source-project.json)
- The baseline ensemble ran three independent peers and a separate chair.
  All nine aggregate values verify. The three content candidates used inline
  references and omitted the required BibTeX database and style commands.
  The bibliography gate rejected each before review, so the controller kept
  the initial draft. One separate layout reviewer and editor then executed
  the original single formatting pass. Both received the scope instruction,
  and the editor's placement change passed the source check and compilation.
  [Formatting worklog](formatting-scope-e2e-final/content_refinement_workdir/format_refinement_worklog.json)

The live candidate exercised acceptance of a permitted layout edit. Rejection
of the earlier 42-to-18 citation loss is covered by the archived regression
test. The final teaching note still exceeds the length target, and the PDF
inspection found duplicated provenance text, an overflowing path and a tight
table caption. The reference list and figures are visible. Completion here
verifies execution and scientific-source preservation through formatting.
[Formatting regression](FORMATTING-SCOPE-AUDIT.md)

## Earlier attempt and evidence fix

The first fresh run completed manuscript generation, including a successful
formatting scope check. The editor returned identical source, preserving all
73 references. The driver nevertheless exited 1 because its audit converted
four carriage-return line endings when reading the section writer's prompt.
The saved file and planned stdin had identical hashes. The failed manifest and
artifacts were retained locally. An independent check with the corrected reader
verified the manuscript and transport evidence from that attempt.
[Recheck receipt](formatting-scope-first-reaudit.json)

R031 records the fix. Reading the retained UTF-8 prompt without newline
conversion preserves the exact comparison in all supported transports. The
new regression accepts mixed line endings when they match and rejects altered
ones. All 327 tests passed. Pinned upstream source and original parser and
retry function checks also passed. The completed run above started fresh from
the frozen corrected installation. [Test result](formatting-transport-tests.log)
