# Independent conformance audit

**Result: PASS for the real supplied-figure workflow, with the scope and version limits below.**

Audited `validation/real-e2e-final` after its manifest reached `completed` on
2026-11-15. The current `paper-orchestra/scripts/summarize_trace.py` exits 0 with
`evidence_valid: true`, no errors and no warnings. This audit also independently
read the raw invocation events, recomputed scores and file hashes, and compared
the accepted and rejected manuscript versions. It did not modify the run.

| Observed evidence | Independent result |
| --- | --- |
| Separate execution | 34 `codex exec --ephemeral` launches, 34 distinct recorded PIDs, 34 unique session IDs, and 34 completed turns with token-usage records. Commands are actual Codex invocations; no fixture executable or mock executor appears in this run's dispatch records. |
| Responsibilities | 1 capability probe, 1 outline, 15 literature discoveries, 1 literature synthesis, 1 section writer, 9 peer reviewers, 3 area chairs, 2 content editors and 1 formatting reviewer. |
| Parallelism | Literature discovery reached 10 simultaneously active agent invocations, matching the authors' discovery pool. All 15 discovery invocations have concrete completed search-tool evidence. |
| Dependency order | Successful Outline → HybridLiterature → SectionWriting → ContentRefinement stage spans occur in dependency order. |
| Handoffs | The enriched outline, literature-filled template and bibliography are byte-identical to their section-writing destinations. The raw section draft is byte-identical to the refinement input. The stage snapshots' handoff hashes agree. |
| Reviewer ensemble | Three complete ensembles, each consisting of three sequential independent reviewers followed by a separate chair. All reviewer/chair call spans are strictly sequential. No failed ensemble occurred in this run. |
| Numeric aggregation | Recomputed all nine bounded integer means for each ensemble: all 27 values match the saved aggregate reviews. Overall scores are 2, 3 and 3. Chair prose remains separate from these deterministic score calculations. |
| Artifact integrity | All 41 non-manifest artifacts listed in the completed manifest match their recorded SHA-256 values. The manifest's own intermediate snapshot hash is excluded from this check. |
| Compiled output | Baseline, v1 and v2 each produced PDFs. The delivered final PDF opens as a four-page PDF and matches the manifest hash. |

## Acceptance, reversion and formatting observed

`content_refinement_worklog.json` records v1 as
`ACCEPTED_SCORE_INCREASE`: Overall 2 → 3, subaxis gain 2 and drop 0.
It records v2 as `REJECTED_DEGRADATION`: Overall remains 3, gain 0 and drop 1
(Clarity 4 → 3). The controller stops the content loop after this second round.

Both `final_refined_paper.tex` and the delivered `final_paper.pdf` are
byte-identical to accepted v1; the final TeX differs from rejected v2. This
directly verifies retention of the previous accepted version, not merely a
worklog label.

There is exactly one formatting-review invocation. Its parsed result reports
`None` for Figure 1 and Table 1, with an empty `other_issues` list. No formatting
editor, formatting candidate compilation, or fourth peer ensemble follows it.
The final source also equals `format_candidate_v0.tex`. This matches the
authors' single formatting pass and no-issue stopping behavior.

## Limitations and provenance

- Semantic Scholar returned HTTP 429 on 95 requests and HTTP 200 on 10. The
  final citation map contains two enriched papers. The authors' no-retry and
  skip-on-failure enrichment behavior was retained; this run does not demonstrate
  comprehensive literature coverage.
- This is the upstream default **supplied-figure** path. There are no image-tool
  events. Generated-figure branch parallelism and image failure handling have
  deterministic tests, but no real diagram-generation tool run is claimed. The
  reusable runtime requires a configured image-tool executable for that mode.
- The toy arithmetic inputs are synthetic demonstration materials. Actual
  agent execution and low reviewer scores establish workflow evidence, not
  scientific novelty, manuscript correctness or reproduction of the authors'
  paper-quality results. I found no mocked model/tool responses in the real
  dispatch records; controlled test fixtures are stored separately.
- Raw event files are valid JSONL when read using physical LF delimiters. One
  search result contains literal Unicode U+0085 characters inside a valid JSON
  string. Python `str.splitlines()` incorrectly fragments that record; the
  final auditor reads physical LF records and reports no malformed lines.
- The manifest pins launch hashes for four emitter files. Their current hashes
  differ because runtime/audit hardening continued while the run was active.
  The passing evidence audit ran **after** execution with the final tooling.
  It validates the recorded execution; it does not claim that every later
  in-process enforcement change or failure branch executed in the launched
  process.

Current source verification against upstream commit
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56` passes: 20 bundled file hashes,
22 original source files, and all seven original Gemini parser/retry function
ASTs. Scientific prompts and controller decision code remain preserved as
documented in the adaptation ledgers.

The independent trace-audit suite now has **25 passing tests**, including
failed-ensemble recovery, corrupted/missing evidence, overlapping reviewers,
false search claims, genuinely malformed extra records, and literal U+0085
inside valid JSONL. Those tests use labelled fixtures and are distinct from
the real execution inspected above.
