# Choose models when invoking PaperOrchestra

The skill asks for model choices before starting unless the user already supplied
them or explicitly selected a saved/previous profile. Ask in chat; the bundled
driver is noninteractive. Recommendations are optional; no profile is silently
chosen. The bundled `profiles/openai-balanced.json` is an explicit starting point
for Codex. Provider comparisons and their dated official sources are documented
in the [repository README](https://github.com/DavidZenz/PaperOrchestra#recommended-models-by-agent-type);
the recommendations are not a measured PaperOrchestra quality comparison.
For actual native backends, per-role effort and mixed execution targets, read
[native runtimes](native-runtimes.md). The examples below describe the compatible
schema-1 model-only interface; schema 2 adds backend/model/effort objects.

Offer one setup question: use the current Codex CLI default for all roles, choose by
agent type, or load a saved profile. If the user chooses per-type settings,
collect the following assignments together, allowing a shared default and
individual overrides. Only ask for missing choices. Do not request another
confirmation once the user has supplied the configuration and authorized a run.
For partial natural-language assignments, capture a fallback for the remaining
roles. Supplying a profile accepts its documented fallback/inheritance behavior.

| Profile group | Independent roles |
| --- | --- |
| `discovery` | `literature-discovery` |
| `writing` | `outline`, `literature-synthesis`, `section-writer`, `content-editor` |
| `figure_planning` | `figure-retriever`, `figure-planner`, `figure-stylist` |
| `figure_code` | `ggplot2-visualizer`, `tikz-visualizer` |
| `figure_review` | `figure-critic`, `figure-captioner` |
| `peer_review` | `peer-reviewer` (three sequential separate invocations per ensemble) |
| `meta_review` | `area-chair` |
| `formatting` | `format-reviewer`, `format-editor` |

`runtime-probe` can be overridden individually; otherwise it uses the fallback.
Missing PaperBanana assets still skip the retriever model call under upstream
rules. Model configuration does not force an otherwise skipped role to execute.

## Profile format

This JSON file belongs to PaperOrchestra; it is distinct from the Codex CLI's
native TOML configuration profile. Replace the uppercase example values with
actual model IDs available in the user's account/provider:

```json
{
  "schema_version": 1,
  "name": "my-paper-models",
  "default": "WRITING_MODEL_ID",
  "groups": {
    "discovery": "DISCOVERY_MODEL_ID",
    "figure_code": "CODE_MODEL_ID",
    "peer_review": "REVIEW_MODEL_ID",
    "meta_review": "META_REVIEW_MODEL_ID",
    "formatting": "FORMAT_MODEL_ID"
  },
  "roles": {
    "tikz-visualizer": "TIKZ_MODEL_ID"
  }
}
```

The simplest valid profile is `{"default": null}`: the user explicitly chooses
the current Codex CLI configuration for every role. An omitted entry inherits
the fallback; an explicit `null` entry selects the Codex configured default for
that role/group, even when another fallback model was supplied.

Resolution, highest priority first:

1. `--role-models-json` individual role override.
2. Profile `roles` entry.
3. Profile `groups` entry.
4. Existing `--model-map-json` upstream-name mapping.
5. `--model` shared fallback.
6. Profile `default`.
7. Current Codex CLI model.

`content-or-format-editor` remains accepted as a compatibility role key applying
to both editor types. Specific `content-editor` or `format-editor` entries in
the same mapping take priority. Legacy trace labels are retained; separate
`model_routing.routing_role` metadata records the actual model-choice slot.

## Preview, run and reuse

```bash
python /absolute/skill/scripts/run.py --model-profile /absolute/models.json \
  --show-model-plan
python /absolute/skill/scripts/run.py --materials /absolute/materials \
  --template /absolute/template --output /absolute/new-output \
  --model-profile /absolute/models.json --use-plotting
```

The preview makes zero model calls and requires neither paper inputs nor output
directory. It checks configuration structure and routing, not service access.
Unknown roles/groups, malformed JSON and invalid model values fail before paid
execution. An unsupported or unavailable model is surfaced by actual Codex
execution; no cheaper/different model is silently substituted on failure.

Each run retains:

- The full policy and resolved plan in `run.json`.
- Reusable flat role settings in `execution/model_profile.json`.
- Original supplied profile bytes in `execution/model_profile.source.json`,
  when a profile file was supplied. Editing that external file during a run does
  not change already selected settings.
- Per-attempt model, role/group, selection reason and actual `--model` argv in
  `request.json` and the trace. Retries keep the selected model.

Reuse the saved `execution/model_profile.json` with `--model-profile` next time.
Explicit model IDs make choices repeatable. A `null` entry intentionally inherits
the current CLI configuration and therefore does not pin a model across machines
or later configuration changes. Full LLM output remains stochastic either way.

## Runtime boundaries

The adapter uses the CLI's per-invocation `--model` option, documented in the
[official CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
and checked against the installed CLI's `codex exec --help`. It does not switch
the parent chat model. Available models depend on the configured provider,
account and workspace; original Gemini names are provenance/mapping keys, not
automatically available Codex targets.

Without explicit effort overrides, existing runtime effort settings continue to
apply. Do not silently change them when selecting models. Discovery needs live-search support;
section writing, revision, figure critique/captioning and visual reviews need
image/PDF-context support. Choose compatible models or report the exact failure.
Changing model IDs is an inference-environment adaptation (R023), not a change
to the upstream dependency graph, role responsibilities, reviewer count,
aggregation, revision acceptance/reversion, retries or stopping rules.

Native backend adapters launch Codex, Claude Code, Antigravity and Mistral Vibe.
Schema 2 selects the runtime explicitly; model names alone never guess a provider.
Each runtime requires its own authentication and compatible model/tool/media
support. Antigravity's own orchestration must not substitute for the pinned
PaperOrchestra controller. See the current validation report for what actually
executed and [native runtime limits](native-runtimes.md) before choosing a profile.
