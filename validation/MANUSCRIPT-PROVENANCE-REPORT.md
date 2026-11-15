# Exact manuscript figure provenance

This update implements the user's requirement that manuscript references name
the exact R/ggplot2 and TikZ sources that produced its selected figures.
The scientific body, experiment and original control rules are preserved.

## Corrected manuscript

The corrected source project is [output/pdf/manuscript](../output/pdf/manuscript/),
with a [compiled manuscript](../output/pdf/manuscript/final_paper.pdf),
[LaTeX source](../output/pdf/manuscript/final_paper.tex),
[selected-source manifest](../output/pdf/manuscript/figure_provenance.json) and
[correction record](../output/pdf/manuscript/source_correction.json).
The [complete source project archive](../dist/corrected-manuscript.zip) includes
the manuscript, both exact figure sources, export wrapper and rendering metadata.

The two alternative `filecontents*` figure recipes have been removed. A visible
source appendix references each actual figure, its exact source filename and
SHA256, the R export wrapper/hash, and rendering/session metadata. The referenced
files under `figure_code/` are byte-identical copies of the original successful
worker/render artifacts:

- [R/ggplot2](../output/pdf/manuscript/figure_code/fig_intercept_error/source.R)
  and [export wrapper](../output/pdf/manuscript/figure_code/fig_intercept_error/worker.R).
- [TikZ](../output/pdf/manuscript/figure_code/fig_residual_workflow/source.tex).

The original five pages are pixel-identical to the accepted historical PDF.
The sixth page contains the new source appendix; filenames, underscores and
hashes are visible and copyable. All pages were inspected without observed
clipping/overlap. Both embedded figure images are unchanged. The scientific
body is also unchanged as LaTeX text.

[Published-source replay](published-source-replay/replay.json) executes copies
of these published source files in a fresh directory. Both sources and both
resulting previews match exactly, with **zero model calls**. The corrected
manuscript is an explicitly requested deterministic edit: it has no new model
calls or peer reviews, and does not reuse the historical scores as scores for
the added appendix. The original run remains untouched.

## Pipeline invariant

The selected preview's hash and figure ID resolve the actual successful source,
including the authors' last-valid-image behavior. After the literature/plot
join, the driver publishes `figure_provenance.json` and stable exact source
copies to both manuscript workspaces. Each section/content/format worker gets
the manifest, actual source and wrapper text, checksums and file snapshots.

Complete LaTeX results receive the same deterministic source appendix before
the original controller consumes them. Alternative figure recipes are replaced
with these references. Unrelated arithmetic, algorithms, JSON worklogs and
empty/incomplete responses retain their original behavior. The formatting
editor's raw-response channel is handled too. Original worker responses and
upstream parser results remain intact alongside effective manuscript artifacts.

Compilation verifies the provenance and snapshots the exact candidate and
source files; it does not rewrite the candidate. Review, acceptance, reversion
and final source/PDF selection therefore operate on the same effective document.
Earlier source manifests and snapshots remain auditable across whole-paper
retries. No extra model call, critic round, reviewer or revision is introduced.

## Tests and source verification

[The full test log](manuscript-provenance-tests.log) records **160 passing tests**.
The 45 added tests cover source selection/publication, initial/content/format
handoffs, raw/effective transformation, worklog preservation, rejection/reversion,
compile failure, empty-output stopping, tampering, per-attempt retry provenance,
retained-review aggregation, legitimate template/prose preservation, actual
selected-image embedding, and a real pdfLaTeX/PDF filename/hash round-trip.
Fixture model responses remain explicitly controlled tests, not real inference.

[Installed source verification](manuscript-provenance-installed-source-verification.json)
passes 20 bundled hashes, 22 actual pinned upstream files and seven original
parser/retry AST comparisons at commit
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56`. Copied scientific prompt/controller
files remain unchanged. The installed skill validator also passes.

The independent audit is recorded separately in
[MANUSCRIPT-PROVENANCE-AUDIT.md](MANUSCRIPT-PROVENANCE-AUDIT.md).

## Exact installed-build validation

The tested source and installed skill contain the same **43 files**, frozen at
SHA256 `735b4837fe9a5a8a521af16cc19634a55297e8297679e517addcbfd24d027026`.
The [freeze record](manuscript-provenance-freeze.json) records the full file map,
test-log hash and portable archive hash. The launch, execution snapshot,
completion, current installed copy, workspace source and portable archive all
match. No package files were changed during or after the successful run.

The initial `provenance-e2e/` development run was interrupted before changing its
frozen build. Forward checks found an overbroad recipe guard; its source, traces,
freeze and archive are retained and excluded from successful-run claims. The
guard was narrowed and regression-tested before this new build. A real initial
TikZ font-package failure also motivated explicitly naming pdfLaTeX and built-in
fonts in the visualizer task (A005).

**Fresh real run completed:** [provenance-e2e-final](provenance-e2e-final/) ran the
exact installed entrypoint with `--use-plotting` and provenance policy version 1.
It exited **0**, with `status: completed`, `skill_unchanged: true` and a clean
in-process audit. The independently invoked installed
[trace auditor](provenance-e2e-final-trace-summary.json) also reports
`evidence_valid: true`, no errors and no warnings.

| Evidence | Observed result |
| --- | --- |
| Independent agents | 57 actual process launches, distinct sessions and completed attempts, including one capability probe; no failed model attempts |
| Parallel graph | Literature and plotting overlap; both finish before section writing; both figure pipelines run concurrently |
| Visualizers and stopping | Four R and four TikZ workers, six critics and two captioners; original three-critique limit followed |
| Real render failure | The last TikZ regeneration fails because its source redefines `\columnwidth`; upstream retains the previous valid preview, and the manifest selects the actual third TikZ source, not the newest failed source |
| Exact source propagation | Initial writer and both content revisers each receive the same manifest and ten exact source/rendering files |
| Before-review assembly | Three original/effective result pairs and three checked compilation snapshots; original responses and JSON worklogs retained separately |
| Reviewer ensemble | Three full ensembles, each three sequential separate peers plus a separate chair; all 27 numeric aggregate fields match upstream means |
| Revision one | Overall 3 → 3, gain 2/drop 0 (Quality and Presentation): accepted and continued |
| Revision two | Overall 3 → 3, gain 0/drop 1 (Quality): rejected, reverted to v1, stopped before v3 |
| Formatting | One review, no critical issues; no formatting editor and no extra peer re-review |
| Final selection | Final TeX/PDF byte-identical to accepted v1; rejected v2 retained |
| Actual figures and references | Initial, v1 and v2 PDFs all contain both selected JPEGs and exact source paths/hashes; final audit verifies visible source/wrapper paths/hashes and actual image bytes |

[Fresh figure replay](provenance-e2e-final-replay/replay.json) re-renders all
**seven successful attempts** with **zero model calls** and **identical previews**.
The failed fourth TikZ attempt remains retained with its source/error and is
correctly excluded from successful replay. The seven successful renders do not
imply eight successful attempts or an additional critique after the last render.

[Fresh PDF checks](provenance-e2e-final-pdf-checks.json) verify every candidate's
source/image pairing, accepted-version equality and the final six-page render.
All six final pages were visually inspected without observed clipping/overlap;
no manual edits were applied to the fresh workflow's manuscript.

The real run exercises tie acceptance, later degradation/reversion, early content
stopping, single-pass formatting and last-valid-image retention. Controlled tests
cover the remaining retry/failure/cap and formatting-editor paths; a real
formatting-editor invocation is not claimed when the upstream reviewer requests
no changes.

Runtime limits remain explicit. The 18 live discovery workers produce 124 real
Semantic Scholar responses: 119 HTTP 429 and five HTTP 200; zero papers survive
the original enrichment/filters. No citations are fabricated. Missing PaperBanana
resources take the original empty-example fallback, without inventing a retriever
model call. This finite synthetic calculation and Overall 3 scores demonstrate
workflow/provenance behavior, not publication quality. Saved-code replay is tested
in the recorded R/TeX environment; fresh LLM generation remains stochastic and
cross-platform pixel identity is not established.

## Adaptation and historical evidence

[R022](../paper-orchestra/references/adaptations.md) records the additional
source handoff, effective-result assembly, snapshots and verification.
[A004](../paper-orchestra/references/scientific-adaptations.md) separately records
the visible provenance appendix and figure-recipe replacement as a
user-authorized manuscript input/output adaptation. A005 records the explicit
TikZ engine/font constraint. D005 identifies the separate
correction of the existing manuscript. Scientific guidance, venue prompts,
review rubrics, numeric aggregation and revision/stopping code are unchanged.

The [previous frozen R/TikZ report](INSTALLED-CODE-REPORT.md) remains evidence for
the earlier 41-file build and its 65-session run. That report's alternative-recipe
caveat motivates this correction; it does not describe the corrected manuscript.
Its archive is retained as `dist/paper-orchestra-r-tikz-8eaf7371.zip`.
