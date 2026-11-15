# PaperOrchestra for Codex

This project ports **PaperOrchestra: A Multi-Agent Framework for Automated AI
Research Paper Writing**, by **Yiwen Song, Yale Song, Tomas Pfister and Jinsung
Yoon (Google Cloud AI Research)**. The original workflow, roles, prompts and
review/revision method come from their [paper](https://arxiv.org/abs/2604.05018)
and [upstream implementation](https://github.com/google-research/paper-orchestra).
This repository contributes the worker-runtime adapters, Codex skill packaging,
reproducible R/ggplot2 and TikZ rendering, provenance checks and validation.
It is an independent adaptation, not an official Google product.

A reusable Codex skill that executes the authors' Python controller with a fresh
Codex, Claude Code, Antigravity or Mistral Vibe process and independent native
session for every model attempt. The upstream controller,
role prompts, reviewer ensemble, numeric aggregation and revision rules are
preserved at commit `ca1b3fa01c2970fc7cda32d16245db38d57b3f56`.

The skill is in [paper-orchestra/SKILL.md](paper-orchestra/SKILL.md). Its
[workflow map](paper-orchestra/references/upstream-map.md),
[intentional adaptations](paper-orchestra/references/adaptations.md), and
[scientific guidance ledger](paper-orchestra/references/scientific-adaptations.md)
distinguish preserved behavior from transport/model changes. This preserves a
workflow, not the authors' exact Gemini sampling behavior or scientific results.

## Run

Use Python 3.11+, the authenticated CLIs selected by your profile, `pdflatex`, and `bibtex`. Create a
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

The default path uses supplied figures. Add `--use-plotting` for separate native
workers producing R/ggplot2 plots and LaTeX/TikZ diagrams. Rscript with ggplot2 and
TeX with standalone/TikZ must be available. Every figure retains editable source,
an export wrapper, vector PDF and preview; no image-generation model is required.
Native subprocess execution, direct image input and live search must also work.
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
for roles/schema/precedence and [native runtime validation](validation/MULTIRUNTIME-REPORT.md)
for the 294-test suite and actual execution evidence. The prior 57-session Codex
paper remains tied to its original frozen build; new native evidence is tracked
separately.

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

### Native execution backends

The port now launches the actual native CLIs: `codex exec`, Claude Code's
structured print interface, `agy acp`, or `vibe-acp`. Every role attempt gets a
fresh process/session and original inputs. ACP supplies images directly and
retains both directions of native protocol traffic; Claude receives structured
image blocks. The auditor verifies native completion, session, final response,
media and live-search evidence. These are execution adapters, not prompts that
ask one agent to impersonate the team.

Use an explicit backend/model/effort target; a model name alone never guesses
its provider. Each CLI uses its own authentication and account limits. Native
ACP configuration must acknowledge the selected settings; Codex/Claude retain
their explicit native CLI flags. Unsupported models, effort, images or tools
fail explicitly. See
[native runtimes](paper-orchestra/references/native-runtimes.md) for interfaces
and limitations, and the current validation report for live versus controlled
evidence. The older 57-session Codex run belongs to its frozen build.

[Antigravity](https://antigravity.google/docs/models?hl=en) is Google's agent
platform with plan-dependent models. This adapter uses an isolated role worker;
its built-in Orchestrator does not replace PaperOrchestra's controller. Its image
generator is unnecessary for the reproducible R/TikZ workflow.

### Recommended effort

Start at **high for writing, R/TikZ code and scientific review**, and
**medium for planning, figure critique and formatting**. Discovery is model-specific:
Luna high, Claude Haiku medium, Gemini Hydrogen medium, and Mistral Small 4 high.
These are engineering starting points, not measured equivalent compute budgets.
Evaluate lower settings on your own materials before trading quality for cost.

Mistral Large 4 accepts low/medium/high. Small 4 accepts high/none (Vibe calls
none `off`), so its formatting preset also uses high. Mistral-hosted
**Z.ai GLM 5.3** and **GLM 5.3 Flash** accept low/high/max. Base GLM 5.3 is
text-only; Flash is multimodal. The GLM profile uses the base model for literature
synthesis and R/TikZ code, Large 4 for discovery and Flash for image/PDF roles.
A live GLM discovery turn was stopped after it tried forbidden shell access
following successful search; that failure is retained in the evidence. The adapter rejects
image jobs assigned to the text-only model instead of silently invoking a
different vision model. These capabilities and levels come from the official
[reasoning guide](https://docs.mistral.ai/inference/conversations/reasoning),
[GLM 5.3](https://docs.mistral.ai/models/zai-glm-5-3) and
[GLM Flash](https://docs.mistral.ai/models/zai-glm-5-3-flash) pages.

Effort is passed through each runtime's real mechanism: Codex configuration,
Claude `--effort`, Antigravity's acknowledged `thought_level`, or Vibe's scoped
`thinking` configuration. It is not a sentence added to the prompt. Explicit
settings and native acknowledgments are retained; null intentionally inherits
that runtime's defaults. Parent chat/global CLI settings remain untouched.
Automatic team/delegation presets are excluded.

### Optional ready-to-use profiles

- [OpenAI/Codex](paper-orchestra/profiles/openai-balanced.json)
- [Anthropic/Claude Code](paper-orchestra/profiles/anthropic-balanced.json)
- [Google/Antigravity](paper-orchestra/profiles/antigravity-balanced.json)
- [Mistral Vibe](paper-orchestra/profiles/mistral-balanced.json)
- [Mistral-hosted GLM](paper-orchestra/profiles/mistral-glm.json)
- [Mixed runtimes](paper-orchestra/profiles/mixed-example.json)

Each schema-2 profile contains explicit backend, model and effort choices. None
is selected automatically. Preview one, then add it to ordinary run arguments:

```bash
python paper-orchestra/scripts/run.py \
  --model-profile paper-orchestra/profiles/openai-balanced.json --show-model-plan
```

The preview verifies routing, not account access. Check your native model picker
for availability before execution. Model IDs are explicit, but provider weights
behind an ID can change; the run records requested IDs, resolved settings and
observed native events, without guaranteeing immutable weights or identical LLM
outputs. Schema-1 model-string profiles retain their original behavior. See
[configuration details](paper-orchestra/references/native-runtimes.md#profiles-and-cli).

You can mix models across subscriptions by assigning a runtime/model/effort to
each group or role. For example, the mixed profile uses Gemini for discovery,
Codex for writing, Mistral-hosted GLM 5.3 for R/TikZ source and Claude for peer
review. Each CLI uses its own authenticated account; usage is charged against
that runtime's applicable plan or credits. Authentication type matters:
[Claude plan sign-in and API-key billing differ](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan),
[Mistral documents its shared plan allowance](https://docs.mistral.ai/admin/billing-usage/subscriptions),
and [Antigravity documents CLI credits/quotas](https://antigravity.google/docs/cli/credits).
The skill does not transfer entitlements or silently switch accounts/models when
one reaches its limit. The same three-peer/chair structure remains in control.

No cross-provider quality, cost, latency or manuscript-score equivalence has been
established. Model/effort choices can change scores, revisions and manuscripts;
the preserved workflow does not guarantee equivalent scientific quality.

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

Four tests are optional when the separate upstream checkout and older historical
raw run are absent from a fresh clone. The complete development suite passes all
294 tests. Clean-publication-export results and the four optional skips are
documented with their exact input commit and environment in the validation report.

The source verifier checks bundled hashes, the actual upstream Git commit and
working files, and AST equality of the seven original parser/retry functions.
The controller tests mock external effects; transport tests also launch labelled
fixture subprocesses. Controlled traces are explicitly synthetic. Real model
execution evidence for the final installed provenance build is retained in
`validation/provenance-e2e-final/`: 57 separate Codex sessions with source
propagation, aggregation, rejection/reversion and stopping. Its seven successful
figure attempts replayed identically with zero model calls in
`validation/provenance-e2e-final-replay/`. The current full suite has 294 passing tests;
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
Native component records are under `validation/native-capabilities-final-*/`;
the [independent audit](validation/NATIVE-CAPABILITY-AUDIT.md) distinguishes 11
successful components from the failed GLM discovery turn. The new mixed-provider
workflow is recorded separately under `validation/multiruntime-e2e-final/` with
its own frozen skill snapshot. Check [its report](validation/MULTIRUNTIME-REPORT.md)
for completion, exact profile, source replay and observed limits.

The mixed run completed with 65 fresh native workers across all four runtimes,
four reviewer ensembles, original retries and the three-revision stopping cap.
Its five successful figure attempts replayed identically with zero model calls.
The synthetic demo retains a TikZ label overlap after the original compile-only
format acceptance; it is conformance evidence, not a publication-quality claim.

Earlier full raw runs, interrupted diagnostics, renderer scratch directories,
local environments, the separate upstream checkout and QA screenshots remain
local and are excluded from Git. Their historical reports are retained; paths
to excluded raw runs in those reports describe local evidence, not bundled files.
The complete frozen runs provide the public end-to-end evidence. Recorded
absolute paths are historical locations on the validation machine; artifact
bytes/checksums have not been rewritten for publication.

## Cite the original work

Please credit the original authors when using this workflow. This is the citation
provided by the [pinned upstream README](https://github.com/google-research/paper-orchestra/blob/ca1b3fa01c2970fc7cda32d16245db38d57b3f56/README.md#citation):

```bibtex
@article{song2026paperorchestra,
  title={PaperOrchestra: A Multi-Agent Framework for Automated AI Research Paper Writing},
  author={Song, Yiwen and Song, Yale and Pfister, Tomas and Yoon, Jinsung},
  journal={arXiv preprint arXiv:2604.05018},
  year={2026}
}
```

Original source remains Apache-2.0 licensed with its notices retained. Runtime,
scientific-guidance and output-format adaptations are recorded separately in the
linked deviation ledgers above.
