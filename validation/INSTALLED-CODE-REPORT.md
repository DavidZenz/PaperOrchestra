# PaperOrchestra Codex port: installed R/TikZ validation

Validated on 15 November 2026 against [google-research/paper-orchestra at
ca1b3fa01c2970fc7cda32d16245db38d57b3f56](https://github.com/google-research/paper-orchestra/tree/ca1b3fa01c2970fc7cda32d16245db38d57b3f56).

The exact final installed skill completed a real end-to-end run with the parallel
literature/plotting branch, separate Codex processes, R/ggplot2 plots and TikZ
diagrams. Saved-code replay reproduced all eight figure-attempt previews without
any model calls. This establishes the observed workflow and artifact provenance;
it does not establish equivalent manuscript quality to the original models.

## Exact installed build

The entrypoint was `/Users/davidzenz/.codex/skills/paper-orchestra/scripts/run.py`.
The full 41-file installed bundle was frozen before its first model invocation:

`8eaf7371f56354cab08b016d6508f9745a696f83cdea8e88c7662d2dc4035039`

The launch manifest, execution snapshot, completion manifest, current installed
copy and workspace source all match this hash. No package file was edited during
the run or afterward. The portable archive contains those same 41 files; its
SHA256 is `22c5c6c573757ede38a8f78faa1dcbedda84d6211e3b0002f45291e016c6a06f`.
See [freeze record](code-rendering-freeze.json), [package checks](package.json),
and [run manifest](installed-r-tikz-e2e/run.json).

The actual invocation used the installed driver with
`--materials examples/code-figures/materials`,
`--template examples/code-figures/template`, a fresh
`validation/installed-r-tikz-e2e` output, `--cutoff 2026-11`, `--use-plotting`
and `--rscript /opt/homebrew/opt/r/bin/Rscript`; all paths were absolute at launch.
It exited **0**, with `status: completed`, `skill_unchanged: true` and a successful
in-process audit. Authenticated child Codex execution required host escalation.

## Upstream and controlled checks

[Installed source verification](code-rendering-installed-source-verification.json)
checks 20 bundled source/license hashes, 22 actual pinned Git blobs/working files
and AST equality of all seven original Gemini parser/retry functions. Original
controllers, agent files, scientific prompt modules and reviewer implementation
remain byte-exact. The transport and visualizer adapter changes are separately
identified, rather than asserted to be upstream-equivalent inference.

[The test log](code-rendering-tests.log) records **115 passing tests**. Controlled
fixtures exercise handoffs and branch joins, numeric conversion/bounds/rounded
means, independent model retries and backoff, discovery and whole-paper retry
limits, score increase/decrease, tie acceptance/rejection, reversion, compile
failure, empty/error stopping, three-round exhaustion and the single formatting
pass. [Controlled traces](controlled-traces.json) retain explicit examples.
These fixtures are not presented as real model or search results.

The 31 additional tests cover real local R/TikZ rendering, retained code and
wrapper hashes, tampering, last-valid-image/critic behavior, no-model replay,
single-PDF preview consistency for stochastic geoms, frozen bundle/snapshot
checks and generated-figure provenance. Test model responses are labelled mocks.
The [prefreeze independent audit](CODE-RENDERING-PREFLIGHT-AUDIT.md) records three
discovered issues and their verified fixes before installation and freezing.

## Real execution and stopping

[The trace audit](installed-r-tikz-trace-summary.json) and
[raw run](installed-r-tikz-e2e/) retain prompts, responses, child event logs,
process/session IDs, parsed outputs, stage hashes, HTTP results and compiles.
The [independent final audit](INSTALLED-CODE-AUDIT.md) checks the underlying
evidence separately.

| Boundary | Observed result |
| --- | --- |
| Separate execution | 65 actual Codex process launches, 65 distinct sessions and 65 completed attempts; includes one capability probe; no failed agent attempts |
| Parallelism | Literature and plotting spans overlap; both complete before section writing; the two figures also execute concurrently |
| Figure roles | Two planners, two stylists, four ggplot2 visualizers, four TikZ visualizers, six critics and two captioners, each invocation separate |
| Critic stopping | Each figure receives all three critic rounds and four successful renders: initial render plus regeneration after each critique; no extra critique after the final regeneration |
| Handoffs | Four outline/template/bibliography/draft copy pairs match; both selected previews match their source/render artifacts, plotting output and section-writer inputs |
| Reviewer ensemble | Four ensembles, each three sequential independent peers and a separate chair; all 36 numeric fields match the upstream bounded integer rounded means |
| Revision v1 | Overall 3 → 3, subscore gain 1/drop 0: accepted under the tie rule |
| Revision v2 | Overall 3 → 3, gain 0/drop 0: accepted under the tie rule |
| Revision v3 | Overall 3 → 3, gain 0/drop 0: accepted; the three-round cap stops content refinement |
| Formatting | Exactly one review; no critical issues, so no formatting editor or peer re-review |
| Output selection | Final TeX/PDF byte-identical to accepted v3; five pages with both selected figures embedded byte-for-byte |
| Final audit | `evidence_valid: true`, no errors or warnings; the installed in-process auditor passed before completion |

This real run exercises neutral acceptance and the round cap. Rejection,
reversion, failures and retry exhaustion are demonstrated by controlled tests;
they are not claimed to have occurred here. The historical supplied-figure run
also observed real rejection/reversion, but used a different build.

## Reproducible figures and experiment

Every generated figure attempt retains the actual worker-produced `.R` or `.tex`,
render metadata, command/log, vector PDF and JPEG preview. R attempts additionally
retain the export wrapper and `sessionInfo()`. The wrapper fixes seed 0, exports
one PDF, and derives the preview from that same PDF. No raster-only replacement
or manually rewritten figure was used.

Authoritative selected sources are:

- [R/ggplot2 plot](installed-r-tikz-e2e/figure_sources/2d0b5e5b99364a3c85791d3e4bc0b610/source.R), with [export wrapper](installed-r-tikz-e2e/figure_sources/2d0b5e5b99364a3c85791d3e4bc0b610/worker.R).
- [LaTeX/TikZ diagram](installed-r-tikz-e2e/figure_sources/ffbaa274ed3f459a9578874478418d16/source.tex).

The installed `scripts/replay_figures.py` was executed against the completed run,
into a fresh directory. [Replay evidence](installed-r-tikz-replay/replay.json)
records **0 LLM calls**, **8 re-rendered attempts** and
`all_previews_identical: true`. Inputs are checked against the completed run's
artifact manifest, including both R source and export wrapper.

The fixture is a finite five-observation R calculation, with MSEs 9, 2.25 and 0
for offsets 0, 1.5 and 3. Its retained
[experiment script](installed-r-tikz-e2e/raw_materials/reproduce_experiment.R)
was also executed into a fresh directory: observations, metrics, experiment log
and session information all match byte-for-byte, with no model calls. See
[experiment replay checks](installed-experiment-replay/checks.json).

**Manuscript caveat:** the reviser added supplementary `filecontents*` R/TikZ
recipes to the final TeX. Those are alternative reconstructions and differ from
the actual visualizer sources. They are not authoritative provenance and were
not used for the verified figure replay. Use `figure_sources/` and the installed
replay command to reproduce the figures actually embedded in the manuscript.
No manual manuscript correction or extra revision was inserted into the workflow.

[PDF checks](pdf-checks.json) record final-version equality and embedded image
hashes. All five pages were rendered with Poppler and visually inspected; no
clipping or overlap was observed. The table, arithmetic and both figures are
readable; no manual edits were applied.

## Adaptations and practical limits

The user explicitly replaced the earlier image-model requirement with
R/ggplot2 and TikZ code generation by separate Codex workers. No image-generation
model was used or claimed. The full
[runtime deviation ledger](../paper-orchestra/references/adaptations.md) records
R018–R021 for rendering, retained sources/replay, complete package freezing and
process isolation. The separate
[scientific/output ledger](../paper-orchestra/references/scientific-adaptations.md)
records A001–A003 for visualizer task/code formats and reproducibility artifacts;
copied scientific guidance, venue/domain prompts and manuscript schemas remain
unchanged. D002/D004 record this run's caller-supplied toy fixture and generic
teaching-note template. Search breadth and revision limits were not shortened.

Observed limits:

- All 21 discovery workers performed real live search. Semantic Scholar returned
  **114 HTTP 429 and one HTTP 200**; **zero papers** survived original enrichment
  and filters. The bibliography/citation map are empty. No references were
  fabricated or alternate enrichment/retries inserted. This run validates the
  search execution path, not successful reference coverage.
- PaperBanana example/style assets were absent. The original warning and
  empty-example fallback executed; the retriever function therefore returned
  without a model call. No retriever invocation is invented in the role counts.
- Codex inference/search and PDF transport substitute for the original model/tool
  environment. CLI configured defaults were preserved. Workflow conformance
  cannot guarantee the authors' manuscripts, scores or research quality.
- The recorded environment uses R 4.6.2, ggplot2 4.0.3, TeX Live 2026, Python
  3.15.2 and Codex CLI 0.167.0. Full versions/session details are retained in
  [environment.json](environment.json) and each render. Saved-code replay is
  tested here; dependency restoration on another machine, cross-platform pixel
  identity and byte-identical PDF timestamps are not established. Fresh LLM
  generation remains stochastic.

Earlier evidence remains in [SUPPLIED-FIGURE-REPORT.md](SUPPLIED-FIGURE-REPORT.md),
`real-e2e-final/`, its audit files and `supplied-figure-*.json`. The interrupted
`real-e2e/` diagnostic remains excluded from success claims. The earlier
launch-versus-late-hardening limitation does not apply to this frozen run.
