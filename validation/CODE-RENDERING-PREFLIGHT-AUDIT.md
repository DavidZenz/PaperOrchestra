# Independent code-rendering preflight audit

Scope: use the current `paper-orchestra/SKILL.md` and inspect the installed-bundle execution design before freezing the user-approved R/ggplot2 + standalone TikZ adaptation. No paid/live full pipeline was launched for this audit. The root agent will validate the final frozen installed bundle with real separate workers and concurrent literature/plotting branches. Earlier supplied-figure runs cannot establish that result.

## Observed readiness

- Every model attempt is dispatched through a new `codex exec --ephemeral --sandbox read-only` process. Role context for ggplot2/TikZ visualizers and figure IDs is propagated with context variables. Successful CLI execution requires one independent session and completed turn; discovery separately requires completed live-search tool events.
- The source controller still creates the upstream literature/plot branch pool (2), discovery pool (10), figure pool (5), three sequential reviewers and one area chair. Runtime wrappers observe stage/handoff state and replace only the documented visualizer boundary. Renderer failures return `None` to the original critic loop rather than adding an independent repair loop.
- R code and deterministic export wrapper are retained, along with PDF, JPEG, source hashes, command/log and R session details. TikZ code is retained and compiled in a separate pdflatex process with shell escape disabled; one-page output is required.
- The driver snapshots installed skill files before the first agent, verifies the snapshot against launch state, and compares finish state to launch before acceptance. Compiled bytecode/cache exclusions are explicit. The snapshot is independent of the earlier per-file upstream source lock.
- No-model replay checks source/wrapper hashes, reruns actual tools in a new directory and compares JPEG previews. Source-backed selection checks worker response against source, render output against selected image, and selected image against the section writer's handoff.
- Adaptation ledgers clearly separate visualizer output-language changes A001/A002, reproducibility artifacts A003, operational transport differences, and unchanged upstream scientific guidance. Requested TikZ aspect ratio is presently a task input, not an enforced output canvas constraint; that distinction is documented.

## Pre-freeze findings and verified fixes

All three findings below were fixed before freeze and independently re-probed. They are retained as an audit trail, not open blockers.

### 1. Mutable renderer metadata can defeat the summary's wrapper integrity check

Local controlled probe used the real-R-rendered fixture from `tests.test_frozen_plot_audit.FrozenPlotAuditTests`. Baseline `summarize_trace.summarize` returned `evidence_valid=true`. After rendering, the probe appended a comment to retained `worker.R` and updated `render.json.files_sha256["worker.R"]` to the changed hash. The immutable completed-run `run.json.artifacts` entries were left untouched. The summary still returned `evidence_valid=true`, with no errors.

The summary checks the wrapper against mutable local `render.json` without anchoring that metadata/wrapper to the final run manifest. Replay does use the run manifest and would reject this retained bundle. Thus summary acceptance and replay acceptance disagree. The final audit should require selected render metadata and retained renderer inputs to match the completed manifest before accepting their internal hashes.

Observed result:

```json
{
  "baseline_evidence_valid": true,
  "mutated_evidence_valid": true,
  "errors": []
}
```

### 2. The TikZ backend accepts a non-TikZ article as a successful diagram

Local source was exactly:

```latex
\documentclass{article}\begin{document}A valid article page containing no TikZ diagram.\end{document}
```

`write_sources(..., backend="tikz", aspect_ratio="21:9")` followed by the real `render_saved` compiled this to a one-page PDF/JPEG and returned success. There was no standalone class or TikZ diagram. The adapter's active task explicitly requires a standalone TikZ document, but its mechanical acceptance checks only compiler success and one page. A source-contract gate should reject this before it can be recorded as a successful TikZ diagram. The measured page aspect ratio was 0.70707098; requested ratio 21:9 is not the blocker because the documented adaptation currently keeps ratio as a task input.

### 3. R's vector PDF and reviewed JPEG can contain different stochastic plot geometry

The R wrapper sets one seed, sources code once and calls `ggsave` twice. Each save builds a ggplot separately. Standard stochastic geoms/statistics can consume RNG independently, so the saved vector PDF may differ from the JPEG that the critic and manuscript see. A local `geom_jitter(width=.2,height=0)` probe under the same initial `set.seed(0)` yielded x coordinates:

```text
first build:  0.9838310 1.1898530 0.8386650
second build: 0.9413873 0.9412170 1.1455250
identical: FALSE
```

A full replay can still reproduce this pair, but the pair does not depict one identical rendered figure. Restore the same RNG state before both exports or create the preview from the actual native PDF. Either is a renderer/output adaptation, with no need to modify upstream scientific prompts, pools, reviewer aggregation or critic stopping.

## Narrow independent recheck after fixes

- The same retained-wrapper-plus-metadata mutation now makes `evidence_valid=false`; the untouched source-backed baseline continues to pass. The summary anchors render metadata and each input against completed `run.json.artifacts` before trusting internal hashes.
- The same non-TikZ article now raises `ValueError: TikZ source must use the standalone document class` before compiler launch. Current code checks uncommented standalone declaration and TikZ syntax. A valid standalone document with editable TikZ nodes/paths compiles successfully.
- The R wrapper contains one `ggsave` export. JPEG is rasterized from that actual one-page native PDF at 300 dpi for both backends. The jitter probe's JPEG matches an independently rasterized copy of the same PDF byte-for-byte when using the same DPI metadata; a second execution of the saved R source produces the identical JPEG. The valid TikZ source also produces an identical JPEG on a second execution.
- The focused suite `tests.test_code_renderers`, `tests.test_frozen_plot_audit`, `tests.test_bundle` passed **28 tests** in the earlier pre-fix baseline. That baseline did not establish the three missing invariants, which is why the independent probes mattered. The root/test agent owns new regression tests and final-suite execution after the fixes.

**Pre-freeze result:** the three observed gaps are resolved in the current development bundle. It is ready for the requested freeze/install/full-run/replay validation. This audit does not assert that the final installed end-to-end run has already happened.

## Validation boundary

All probes used temporary directories and real local R/pdflatex tools. The source-generating responses in controlled tests are labelled fixtures and are not represented as live Codex workers. No package/test changes were made by this audit. The only authored deliverable is this report. Remaining required proof is a fresh complete execution from the final exact installed bundle, successful source-backed figure audit, observed literature/plot overlap and no-model replay of both selected R/TikZ figures. The root agent owns that full execution after freeze.
