# PaperOrchestra for Codex

A reusable skill that executes the authors' Python controller with a fresh Codex
process and independent session for every model attempt. The upstream controller,
role prompts, reviewer ensemble, numeric aggregation and revision rules are
preserved at commit `ca1b3fa01c2970fc7cda32d16245db38d57b3f56`.

The skill is in [paper-orchestra/SKILL.md](paper-orchestra/SKILL.md). Its
[workflow map](paper-orchestra/references/upstream-map.md),
[intentional adaptations](paper-orchestra/references/adaptations.md), and
[scientific guidance ledger](paper-orchestra/references/scientific-adaptations.md)
distinguish preserved behavior from transport/model changes. This preserves a
workflow, not the authors' exact Gemini sampling behavior or scientific results.

## Run

Use Python 3.11+, an authenticated Codex CLI, `pdflatex`, and `bibtex`. Create a
virtual environment and install `paper-orchestra/scripts/requirements.txt`, then:

```bash
python paper-orchestra/scripts/run.py \
  --materials /absolute/materials --template /absolute/template \
  --output /absolute/new-output --cutoff 2026-11
python paper-orchestra/scripts/summarize_trace.py /absolute/new-output
```

Materials need `idea_sparse.md`, `experimental_log.md`, and optional
`figures/{info.json,images...}`. The template needs `template.tex`, `guidelines.md`
and its assets. Supply other material filenames with the documented CLI flags.
Use a fresh output directory. Child agents are read-only and do not resume or
share conversations. Each original API retry gets its own fresh invocation.

The default path uses supplied figures. Add `--use-plotting` for separate Codex
workers producing R/ggplot2 plots and LaTeX/TikZ diagrams. Rscript with ggplot2 and
TeX with standalone/TikZ must be available. Every figure retains editable source,
an export wrapper, vector PDF and preview; no image-generation model is required.
Codex CLI subprocess execution and live search must also work.
No single-agent fallback is provided. This desktop host requires escalation to
launch the authenticated child processes; the skill does not bypass its host's
permissions.

Copy `paper-orchestra/` into a Codex skill discovery directory such as
`~/.codex/skills/paper-orchestra` to reuse it. Keep its relative directory structure.
The skill is self-contained; `upstream/`, tests and demonstration data are
development/validation resources, not dependencies of installed runs.

Generated figure sources are under `figure_sources/`. Re-render without an LLM:

```bash
python paper-orchestra/scripts/replay_figures.py /absolute/run \
  --output /absolute/fresh-replay --rscript /absolute/Rscript
```

The driver snapshots and hashes the entire installed skill before generation
and verifies it unchanged before completion. Rendering replay uses saved source;
a new model-generated run is stochastic. Exact pixel replay is checked in the
recorded environment, while portable PDF metadata identity is not promised.

## Choose child models

The skill asks for model preferences when a paper invocation supplies none.
Choose one default, models by agent type, or a saved JSON profile; individual
roles can override group choices. A supplied profile is reused without another
setup question. The driver remains noninteractive:

```bash
python paper-orchestra/scripts/run.py --model-profile /absolute/models.json --show-model-plan
```

This preview makes zero model calls. Use the profile with the ordinary paper-run
arguments to execute it. See [model selection](paper-orchestra/references/model-selection.md)
for roles/schema/precedence and [validation](validation/MODEL-PROFILES-REPORT.md)
for the 183-test check. The prior 57-session paper run remains tied to its original
frozen build; this configuration update did not launch another manuscript run.

## Recommended models by agent type

Recommendations checked **15 November 2026**. These assignments are engineering
judgments based on the providers' published capabilities, not results of a
PaperOrchestra model comparison. Start with the OpenAI profile for this Codex
port; use your own domain-specific evaluation before treating a lower-cost
assignment as equivalent to a stronger model.

| Agent type / profile group | OpenAI | Anthropic | Google Gemini | Mistral |
| --- | --- | --- | --- | --- |
| Literature discovery (`discovery`) | GPT-6 Luna | Claude Haiku 5.5 | Gemini 4 Hydrogen | Mistral Small 4 |
| Outline, synthesis, sections, revision (`writing`) | GPT-6.1 Sol | Claude Sonnet 5.5 | Gemini 4 Argon | Mistral Large 4 |
| Retrieval, planning, styling (`figure_planning`) | GPT-6.1 Sol | Claude Sonnet 5.5 | Gemini 4 Argon | Mistral Large 4 |
| R/ggplot2 and TikZ source (`figure_code`) | GPT-6.1 Sol | Claude Sonnet 5.5 | Gemini 4 Argon | Mistral Large 4 |
| Figure critique and captions (`figure_review`) | GPT-6.1 Terra | Claude Sonnet 5.5 | Gemini 4 Argon | Mistral Large 4 |
| Three separate peer reviews (`peer_review`) | GPT-6 Astra | Claude Opus 5.5 | Gemini 4 Carbon | Mistral Large 4 |
| Separate meta-review (`meta_review`) | GPT-6 Astra | Claude Opus 5.5 | Gemini 4 Carbon | Mistral Large 4 |
| Layout review and LaTeX fixes (`formatting`) | GPT-6.1 Terra | Claude Sonnet 5.5 | Gemini 4 Argon | Mistral Small 4 |

The rationale is to spend more reasoning capacity on scientific judgment, keep
capable general models on manuscript synthesis and executable figure code, and
use efficient models for the many independent discovery requests. Visual review
requires image understanding; discovery requires actual live search. Faster
models can still miss papers or produce invalid structured output, consuming the
original retry budget. R and TikZ render the figures from retained code regardless
of the model that wrote it.

This mapping draws on the official [OpenAI model guidance](https://learn.chatgpt.com/docs/models?surface=cli),
[Anthropic model comparison](https://platform.claude.com/docs/en/models/overview),
[Gemini catalog](https://aistudio.google.com/docs/models), and
[Mistral Large 4](https://docs.mistral.ai/models/mistral-large-4-0) /
[Small 4](https://docs.mistral.ai/models/mistral-small-4-0-26-03) documentation.
Those sources establish advertised capabilities and model names; the role
assignments above are this port's recommendations.

For a lower-cost OpenAI configuration, use Sol for the peer reviewers and chair
as well. For particularly difficult scientific synthesis or R/TikZ work,
consider Astra for the affected roles. With Anthropic, Opus is the quality-first
upgrade for writing/code; Fable 5.2 is an option for demanding reasoning after
evaluations show Opus insufficient. With Gemini, Argon is the lower-cost
alternative to Carbon for review, and 3.8 Flash is an older efficient alternative
where Hydrogen is unavailable. These are explicit user choices; the runtime does
not downgrade a failed call. Three peer reviews remain three independent
invocations with the selected peer model, followed by the separate chair. Numeric
aggregation and all acceptance/reversion/stopping rules stay in Python.

### What can execute today

**Implemented and tested: Codex CLI workers.** The profile passes model IDs to
`codex exec --model`. It does not select a provider, configure API credentials,
translate APIs, or launch Claude Code, Antigravity, or Mistral Vibe. A name in the
table is not a promise that Codex can execute it. The Anthropic, Gemini and
Mistral columns are advisory targets for future backend adapters; none has been
validated through this port. An existing custom Codex provider/gateway must
independently support the required protocol, image inputs, live search and event
evidence. Mixing provider names in a JSON profile does not implement that bridge.

[Antigravity](https://antigravity.google/docs/models?hl=en) is Google's agent
platform, with a plan-dependent selection of Gemini and other models. For a
future Antigravity adapter, use the Gemini column where available (Argon for
review when Carbon is unavailable), or the corresponding Claude choices. Its
built-in Orchestrator is a different control flow and must not replace
PaperOrchestra's controller. Its image-generation tool is unnecessary for this
R/TikZ workflow. No Antigravity execution adapter is currently shipped.

### Ready-to-use Codex profile

[openai-balanced.json](paper-orchestra/profiles/openai-balanced.json) encodes the
OpenAI column and assigns Luna to the runtime probe. It is optional and is never
selected automatically. Preview it, then add it to the ordinary run arguments:

```bash
python paper-orchestra/scripts/run.py \
  --model-profile paper-orchestra/profiles/openai-balanced.json --show-model-plan
```

The preview verifies routing, not account access. Check your Codex model picker
for availability before execution. Model IDs are explicit, but provider weights
behind an ID can change; the run records requested IDs, resolved settings and
observed CLI events, without guaranteeing immutable weights or identical LLM
outputs. Existing CLI reasoning effort is inherited for every worker; the JSON
schema does not support per-role effort or provider settings. This recommendation
does not change your CLI configuration. Avoid automatic team/delegation presets
when auditing the original role structure.

No cross-provider quality, cost, latency or manuscript-score equivalence has been
established. The recorded full run used its recorded Codex configuration; it did
not test this mixed-model recommendation or the other provider columns.

## Validate

```bash
python -m unittest discover -s tests -v
python paper-orchestra/scripts/verify_upstream.py
python examples/tiny/make_materials.py
```

To compare against the actual pinned upstream checkout as well:

```bash
git clone https://github.com/google-research/paper-orchestra.git upstream
git -C upstream checkout ca1b3fa01c2970fc7cda32d16245db38d57b3f56
python paper-orchestra/scripts/verify_upstream.py --source upstream
```

The source verifier checks bundled hashes, the actual upstream Git commit and
working files, and AST equality of the seven original parser/retry functions.
The controller tests mock external effects; transport tests also launch labelled
fixture subprocesses. Controlled traces are explicitly synthetic. Real model
execution evidence for the final installed provenance build is retained in
`validation/provenance-e2e-final/`: 57 separate Codex sessions with source
propagation, aggregation, rejection/reversion and stopping. Its seven successful
figure attempts replayed identically with zero model calls in
`validation/provenance-e2e-final-replay/`. The current full suite has 183 passing tests;
160 were present at the time of that full workflow run.

See `validation/REPORT.md` for the observed run, checks and limits. The corrected
existing manuscript and exact source project are under `output/pdf/manuscript/`
and `dist/corrected-manuscript.zip`. The earlier
`validation/real-e2e/` directory is an interrupted diagnostic run retained for
transparency; it is not a successful demonstration. The historical supplied-figure
run remains under `validation/real-e2e-final/` with its separate report. Every
generated figure attempt retains its actual source under `figure_sources/`.
Selected sources are also copied byte-for-byte to the manuscript's
`figure_code/<figure_id>/` directory with `figure_provenance.json`. Writers,
revisers and format editors receive these files. A visible exact-source appendix
is assembled before every complete candidate is compiled/reviewed; alternative
figure recipes are removed and raw/effective results remain inspectable.

Upstream source is Apache-2.0 licensed; the original license and copyright notices
are retained under `paper-orchestra/vendor/`.

## Published evidence

This repository includes the final frozen provenance run, its raw independent
worker sessions, trace, candidates and reviews under
`validation/provenance-e2e-final/`, along with the saved-code replays, controlled
traces and validation reports. Its `execution/skill_snapshot/` and the dated
archives under `dist/` identify which exact build produced each result.
Recommendations and optional model selection were added afterward; the latest
package has regression/preview validation, not a new full manuscript run.

Earlier full raw runs, interrupted diagnostics, renderer scratch directories,
local environments, the separate upstream checkout and QA screenshots remain
local and are excluded from Git. Their historical reports are retained; paths
to excluded raw runs in those reports describe local evidence, not bundled files.
The complete final provenance run is the public end-to-end evidence. Recorded
absolute paths are historical locations on the validation machine; artifact
bytes/checksums have not been rewritten for publication.
