---
name: paper-orchestra
description: Run PaperOrchestra's research-paper writing workflow from an idea, experimental log, LaTeX template and figures using separate Codex agent processes, literature discovery, a reviewer ensemble and score-driven revisions. Use for an end-to-end PaperOrchestra paper run or conformance validation; requires a working Codex CLI and LaTeX tools.
---

# PaperOrchestra

Execute the authors' pinned Python controller through the bundled runtime. Every
model attempt launches a fresh `codex exec` process and independent session.
Do not write the paper yourself, replace the controller with role instructions,
merge reviewers into one session, or fabricate missing agent/tool results.

The upstream pin is `ca1b3fa01c2970fc7cda32d16245db38d57b3f56` from
[google-research/paper-orchestra](https://github.com/google-research/paper-orchestra).
The copied controller and prompts are checked by `upstream-lock.json`.

## Prepare the run

Resolve this skill directory as `SKILL`. Use a Python environment containing
`scripts/requirements.txt`, the authenticated `codex` CLI, `pdflatex`, and `bibtex`.
Install dependencies into an isolated environment if needed; respect the host's
execution permissions. The controller itself uses no Gemini or OpenAI API key.
Semantic Scholar optionally uses `SEMANTIC_SCHOLAR_API_KEY` from the environment.

Obtain the user's material directory, template directory, fresh output directory,
and research cutoff (`YYYY-MM`). The material directory needs `idea_sparse.md`
and `experimental_log.md`; other filenames can be passed explicitly. The template
needs `template.tex`, `guidelines.md` and its styles/assets. For the default path,
provided figures and their `info.json` (`[{"name":"file.png","caption":"..."}]`)
belong under `materials/figures/`. No files from an earlier output are deleted by
the wrapper: choose a new destination for each run.

Read [the upstream map](references/upstream-map.md) for responsibilities, exact
handoffs and control flow, [adaptations](references/adaptations.md) for runtime
differences, and [scientific adaptations](references/scientific-adaptations.md)
before the first run. Scientific guidance is preserved, including the documented
upstream prompt tensions. Visualizer code-language/output substitutions are
explicitly recorded. Do not silently improve or generalize scientific prompts.
An intentional guidance, schema or domain change needs its own recorded
adaptation and must be described as an adapted run.

## Execute

Run the bundled driver with actual absolute paths and the intended cutoff:

```bash
python "$SKILL/scripts/run.py" --materials /absolute/materials \
  --template /absolute/template --output /absolute/new-output --cutoff YYYY-MM
```

The driver first proves that a separate Codex session completes successfully.
It then executes the authors' outline → literature → section-writing → content
and formatting controller. Supplied figures are the upstream default.

For generated figures, add `--use-plotting`. Statistical plots use R/ggplot2;
scientific diagrams use LaTeX/TikZ. Each visualizer is a separate Codex invocation
that writes real source code. A local renderer executes that code and retains
the `.R` or `.tex`, export wrapper, vector PDF, JPEG preview and tool/session
metadata under `figure_sources/`. Do not substitute a raster-only result or a
hand-written replacement for a worker's source. The final audit requires the
retained source to match the actual worker response and selected figure.

After the literature/plot join, the driver resolves each selected preview to its
actual successful render and publishes exact source copies under
`figure_code/<figure_id>/` plus `figure_provenance.json`. Section writers,
content revisers and formatting editors receive those artifacts and checksums.
The runtime maintains a visible Figure source provenance appendix in every
complete manuscript before compilation/review, replacing alternative embedded
figure recipes with references to these exact files. Original worker responses
and effective manuscript results are retained separately. The compiler verifies
the references and source bytes without rewriting candidates. This is the
explicit user-approved manuscript-output adaptation A004; all upstream review,
acceptance, reversion, retry and stopping rules remain in control.

Rscript with ggplot2 and a TeX installation with `standalone` and `tikz` are
required. Use `--rscript /absolute/Rscript` or `PAPER_ORCHESTRA_RSCRIPT` if needed.
The driver also discovers `/opt/homebrew/opt/r/bin/Rscript` when R is not on PATH.
No image-generation model or additional image API key is needed for this mode.
The literature and plotting branches run concurrently; figures also run in
parallel. Missing PaperBanana examples/style guides use upstream's empty-example
fallback. To supply them, set `PAPER_ORCHESTRA_PAPERBANANA` to their directory.

If a required separate process, live-search tool, R/TikZ renderer, PDF context or
compilation capability fails, report the exact limitation. Never fall back to a
single agent. The default runtime needs permission to launch child Codex
processes and access its authentication/network; a sandbox-only probe may fail
even when the desktop agent itself can execute. Ask for host escalation only
when required by that host, with the concrete command and reason.

The upstream five-attempt model retry, three-attempt discovery, three-attempt
paper retry, three content revisions and one formatting pass remain in force.
Reviewers are three **sequential separate agents**, followed by a separate chair.
The controller computes the bounded integer means and makes acceptance/reversion
decisions. Never override a rejected revision or retry beyond these limits.

## Inspect and deliver

Check the exit status and `run.json`: only `completed` is a successful paper run.
`preflight_ok` only proves runtime capability. A produced PDF with a failed run
manifest is not a successful result. Inspect `execution/trace.jsonl`, individual
`execution/invocations/*/{request.json,prompt.txt,response.txt,events.jsonl}`,
peer reviews and refinement worklogs. Fresh process/session evidence is required
for every model call. Discovery must contain actual `web_search` events.

Before its first model call, the driver snapshots the entire installed skill
under `execution/skill_snapshot/` and records its content hash. It checks the
same installed files again before accepting completion. Do not edit the installed
skill during a validation run. If a fix is required, retain the failed run,
finish/test/install the fix, and start a fresh full run of that final bundle.

Run `scripts/summarize_trace.py /absolute/output` to check the handoff hashes,
process/session evidence and reviewer ensemble sequence. Deliver the compiled
`final_paper.pdf`, the source in `content_refinement_workdir/final_refined_paper.tex`,
trace summary, worklogs and limitations. Keep the full output directory because
the TeX needs its bibliography, styles and figure assets.
Deliver its `figure_code/` and `figure_provenance.json` with the manuscript too.
Use these selected sources for the manuscript's reproduction instructions;
never generate supplementary replacement recipes. `execution/manuscripts/`
records raw-parser/effective-result pairs, and `execution/compiled/` retains
the exact source and figure artifacts checked before each complete compilation.

Reproduce figures without another LLM call with:

```bash
python "$SKILL/scripts/replay_figures.py" /absolute/output \
  --output /absolute/new-replay-directory --rscript /absolute/Rscript
```

Replay validates retained input checksums, runs the saved code and compares new
JPEG previews with the originals. It calls no model. Different software, fonts
or platforms can change renders; session/tool metadata defines the tested
environment. Byte-identical PDF metadata across environments is not promised.
A fresh full LLM run is stochastic; replay reuses its saved code.

For source conformance, run `scripts/verify_upstream.py` (bundled hashes), or add
`--source /absolute/upstream-checkout` to compare the pinned source and the copied
parser/retry function ASTs. The development package also includes behavioral
tests and a real demonstration under `validation/`; those are evidence, not
substitutes for executing the user's run.
