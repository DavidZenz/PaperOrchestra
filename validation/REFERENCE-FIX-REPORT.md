# Reference retrieval and bibliography validation

Status: **completed**. The exact frozen installed skill ran end to end, including
the parallel plotting branch. Final PDF: seven pages, **18 resolved references**,
with the visible References list on pages **5–6**.

[Manuscript PDF](reference-fix-e2e-complete/final_paper.pdf) ·
[Exact 18-file source project](../dist/reference-verified-manuscript.zip) ·
[Independent run audit](reference-fix-independent-checks.json)

## Adaptations

- R027: Semantic Scholar primary with two bounded HTTP attempts and run-scoped
  rate-limit circuit; Crossref then OpenAlex verified metadata/abstract fallback.
  Original title/year/cutoff and missing-abstract acceptance conditions remain.
  Raw provider responses and selection/rejection reasons are retained.
- R028/A005: nonempty verified library required before section writing; compiled
  candidates require resolved approved citation keys, valid bibliography output,
  clean citation/BibTeX logs and visible reference metadata. Invalid revisions
  follow original compile-failure handling. Final accepted source/PDF and the
  published PDF are checked again before completion.
- A006: escape literal reserved metadata characters in BibTeX field serialization;
  original citation-key collision mutations remain. No new scientific guidance
  or invented reference content.

These are deliberate adaptations, not exact reproduction of upstream's permissive
reference failure behavior. Agent dependencies, parallel pools, original prompts,
three independent peers plus chair, score aggregation and bounded revision/stop
rules remain. The pinned source verification passes all 20 file hashes and seven
original parser/retry function AST comparisons.

## Controlled checks

[323 tests passed](reference-fix-final-tests.log) in 38.461 seconds. Tests
include raw metadata fallback/cutoff/retry/circuit behavior; empty and mismatched
libraries; unknown/unresolved keys; missing bibliography commands; BibTeX errors;
actual PDF reference rendering; reserved metadata characters; binding final
copies to real compiled candidates; and a controller-success/PDF fixture that
must still fail when references are empty. No external models run in tests.
The earlier bibliography audit remains [historical evidence](BIBLIOGRAPHY-AUDIT.md).

## Frozen live validation

The exact installed skill is at `/Users/davidzenz/.codex/skills/paper-orchestra`.
[Freeze receipt](reference-fix-freeze.json): 60 files, bundle
`157a4eb83eb7ad24b0738f55b3088af3d79a429625e44834c4e819eb44832330`.
The full run uses `examples/code-figures/materials`, its original template, cutoff
2026-11 and the explicit `reference-fix-models.json` four-runtime profile (same fixture
profile except TikZ source generation uses Codex Sol/high).
It invokes the installed driver with `--use-plotting`; both R/ggplot2 and TikZ
branches execute through fresh native workers.

The earlier `reference-fix-e2e` attempt was externally interrupted during outline
generation to correct duplicate adaptation identifiers. Its original running
manifest and trace are retained; the [external interruption receipt](reference-fix-interruption.json)
records why it is not completed evidence. A second attempt at `reference-fix-e2e-final` was interrupted for the independently
identified partial-date cutoff and credential-log fixes; its separate receipt
is `reference-fix-second-interruption.json`. Both interrupted original artifacts
remain unchanged. The `reference-fix-e2e-verified` attempt used the fully corrected bundle but
was interrupted after two 600-second GLM TikZ timeouts. It produced 53 valid library
records and a separate metadata audit, but is not completed run evidence.
The final full run starts fresh at `reference-fix-e2e-complete` from the same
unchanged installed bundle. `reference-fix-third-interruption.json` records
the reason; `reference-fix-models.json` records the explicit TikZ-only model
substitution. R remains a separate Mistral Vibe worker; the workflow still
exercises all four native backends. No retry/timeout/stopping limits are raised.

## Completed execution evidence

The driver exited 0 with `run.json.status=completed` and `skill_unchanged=true`.
Runtime was 1818.105 seconds. All 60 source, installed, run-snapshot and archive
file hashes match bundle 157a4eb8…. Archive SHA256:
`5db8e70b2b53c10eaf18b2069f631634675ccbca28aa6a60e65d396b39643806`.

- **54 actual native invocations**, all 54 completed with distinct PIDs/native
  sessions:12 Codex, 9 Claude Code, 31 Antigravity and 2 Mistral Vibe.
- Literature and plotting overlap **549.277 seconds**. Actual separate R/ggplot2
  and TikZ workers, critics and captions execute; no source was handwritten or
  substituted after the run. Three successful renders replayed to identical
  previews with **zero model calls**; failed TikZ repairs retain the original
  last-valid-image behavior. [Replay](reference-fix-e2e-complete-replay/replay.json).
- One baseline ensemble: three independent sequential peers plus a separate
  chair; all nine bounded means match. No extra review is fabricated for invalid
  revisions. [Trace audit](reference-fix-trace-audit.json).
- All three content revisions switched to inline references and lacked the
  database/style commands required by the new gate. Their PDFs were rejected
  and removed, consuming the original three rounds. The baseline remained
  accepted, followed by the original single formatting pass. **The gate requires
  the generated BibTeX artifact path even when a model's inline list is nonempty.**
  This stricter output eligibility is part of R028/A005, not upstream behavior.
- The formatting editor shortened the paper and reduced42 initial citations
  to 18. Its accepted PDF/TeX exactly match final copies. Acceptance remains
  compile-only with no post-format peer review, as upstream specifies.
- All 104 manifested run-artifact hashes match; all five manuscript raw/effective
  source handoffs and compile snapshots verify. Exact R/TikZ sources and hashes
  remain referenced in the final PDF. [Provenance audit](reference-fix-provenance-audit.json).

## References and final PDF checks

The library contains 45 records: 19 from Crossref and 26 from OpenAlex. Every library
entry's title, authors, year and upstream-truncated abstract reconstruct from
retained provider JSON; all 525 retrieval-event hashes verify. Cutoff checks pass,
including two month-precision records. The initial template and full draft cite 42
approved keys, above the upstream minimum `int(45*.9)=40`.

The final 18 citations resolve to 18 compiled bibitems; **all 18 reference titles
are visible in the PDF**. Every final cited title matches its intended query
after case/punctuation normalization. Abstract-based review found no material
claim/citation mismatch. One retained library record came from a continuous→binary
outcome title mismatch admitted by the preserved fuzzy rule; it is not cited in
the final paper. This is not full-text scholarly verification or a publication
quality claim. [Library/citation audit](reference-fix-final-library-audit.md),
[bibliography audit](reference-fix-bibliography-audit.json).

Actual HTTP status counts by host: Semantic Scholar 2×429; Crossref 78×200;
OpenAlex 45×200 and 1×429. The legacy trace-summary field named
`semantic_scholar_statuses` aggregates all observed HTTP providers; it must not
be interpreted as S2-only. Correct per-host counts are retained in
[PDF and HTTP checks](reference-fix-pdf-checks.json), alongside source hashes.
Raw trace evidence is unchanged.

Read-only visual review covered all seven final pages: the reference list is
legible on pages 5–6, citation labels resolve, figures remain present and the
exact-source appendix is readable. Spacious figure floats and duplicated source
provenance discussion/appendix remain; no manual layout repairs or extra
scientific/format iterations were performed. The final PDF SHA256 is
`30585e1656de7ebf623899275db1c3c63ef4b31606e6b9221372dbf3f7ede0eb`.
The source-project archive SHA256 is
`8053174fce61ded482a7907011983fb7c4b00a707469cd144373c4cf34422af9`.

A replay invoked before run completion was correctly rejected because its
completed manifest did not yet exist; its log is retained separately as
`reference-fix-replay-premature.log`. The completed-run replay passes. All
interrupted diagnostics remain local and are explicitly not completed evidence;
the final completed run and its replay are included in publication.
