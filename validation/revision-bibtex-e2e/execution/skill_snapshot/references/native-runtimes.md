# Native agent runtimes and effort

The unchanged Python controller owns role order, pools/joins, artifact handoffs,
three sequential independent peers, separate chair, integer aggregation and
revision/reversion/retry/stopping decisions. A backend is only a fresh role-worker
transport. Every original retry creates a new OS process and native session.
No backend's built-in team or orchestration replaces the controller.

## Backend interfaces

| Backend ID | Executable/interface | Model and effort | Task input and native proof |
| --- | --- | --- | --- |
| `codex` | `codex exec --ephemeral --sandbox read-only --json` | `--model`; `-c model_reasoning_effort="..."` | Full prompt, direct `--image` inputs; original thread/turn/tool events |
| `claude-code` | `claude --print --input-format stream-json --output-format stream-json` | `--model`; `--effort` | Full prompt and base64 image blocks; one native init/session and successful result; matched WebSearch call/result |
| `antigravity` | `agy acp --process-per-session` | Acknowledged session `model` and `thought_level` options | ACP-v1 image blocks, new session, config ACKs, native final message/end_turn, matched completed `search_web` call |
| `mistral-vibe` | `vibe-acp` | Process-local model `thinking`; native session options must confirm it | ACP-v1 image blocks, new session, native final message/end_turn, matched completed `web_search` call |

Vibe 3.1 publishes its connector as `connector_web_search_web_search` and reports
the canonical ACP name `connector_web_search.web_search`; both exact interfaces
are supported. Its read-only `search_tool_functions` catalog lookup is allowed
only for discovery and cannot count as search proof. Antigravity 1.5.9 reports
named/query-matched native search completion without retaining a result body;
the proof is successful native status, not a fabricated search-result payload.

Codex remains the default when no new backend settings are supplied. Each runtime
uses its own existing authentication; the adapter neither logs credentials nor
copies authentication files. Install/authenticate the required CLI yourself, for
example `claude auth login`. Tools are restricted to the native live-search tool
for discovery. Other roles receive their input directly and have no reason to
read another worker's directory, write files or delegate. Claude uses safe/
restricted mode with customizations disabled; Antigravity uses a scoped custom
main agent; Vibe disables custom agents, skills, MCP and subagents through
process-local settings. No global model/effort setting is edited.

Mixed subscriptions use separate native authentications. With Claude plan
sign-in, `claude -p` currently draws from plan limits; API-key authentication uses
Console billing/eligible credits
([official explanation](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)).
Mistral documents monthly plan usage shared across Studio/API/Vibe, followed by
the organization's configured credit/overage rules
([subscriptions](https://docs.mistral.ai/admin/billing-usage/subscriptions)).
Antigravity CLI uses its account's model quotas and credits
([CLI credits](https://antigravity.google/docs/cli/credits)). These facts were
checked on 15 November 2026; account/model access and future billing rules vary.
No credential pooling, automatic account switch or quota bypass is implemented.

Codex and Claude do not currently echo the effective effort in the inspected
native completion event. Their retained CLI arguments prove the requested
configuration; the observed-effort field remains null rather than being invented.
ACP workers additionally return model/effort acknowledgments. Neither proves an
equal underlying compute budget across providers.

Antigravity print mode accepts only text blocks, so this adapter uses ACP for all
roles. Vibe's ACP model/thinking setters can persist defaults; this adapter
configures each new process instead and checks its advertised session options
before sending the task. Unsupported choices fail; they are not mapped onto a
different level/model. Native HTTP retries may differ from the original SDK;
the authors' outer five-attempt role retry is unchanged. Vibe's extra output-limit
rewrite loop and background title generation are disabled.

## Profiles and CLI

Schema 1 model-string profiles still work exactly as before. Schema 2 adds
explicit execution targets:

```json
{
  "schema_version": 2,
  "default": {"backend":"codex", "model":"gpt-6.1-sol", "effort":"high"},
  "groups": {
    "discovery": {"backend":"antigravity", "model":"gemini-4-hydrogen", "effort":"medium"},
    "figure_code": {"backend":"mistral-vibe", "model":"mistral-large-4", "effort":"high"},
    "peer_review": {"backend":"claude-code", "model":"claude-opus-5-5", "effort":"high"}
  },
  "roles": {"figure-captioner":{"effort":"medium"}}
}
```

Each field inherits from lower-priority settings unless explicitly supplied.
`model:null` or `effort:null` removes the adapter override and uses the chosen
runtime's configuration. An object that changes backend must explicitly include
both model and effort (null is allowed), so incompatible model/effort choices do
not leak across providers. Backend itself must be a supported explicit string;
use `"backend":"codex"` to reset it. A string/null target changes only the model.

Priority for each field is role override, profile role, profile group, upstream
model map, CLI fallback, profile default, runtime default. The legacy combined
editor key remains available. The current native model/effort snapshots and
launch arguments are saved with each attempt. Reusable schema-2 snapshots retain
all three fields rather than accidentally reverting to the parent CLI defaults.

```bash
python "$SKILL/scripts/run.py" --model-profile "$SKILL/profiles/mixed-example.json" --show-model-plan
python "$SKILL/scripts/run.py" --backend claude-code \
  --model claude-sonnet-5-5 --effort high --preflight-only --output /absolute/new-probe
```

Preview performs no inference and does not prove account access. The driver
checks required executables; its runtime probe proves the selected probe worker,
not every model/tool combination in a mixed profile. Each actual role additionally
checks its native session, completion, final text and required search/media proof.

## Recommended effort

These are starting points, not benchmark results or equivalent compute budgets.
They are encoded in optional dated profiles and never silently selected:

| Role group | OpenAI | Claude Code | Antigravity | Mistral Vibe |
| --- | --- | --- | --- | --- |
| Discovery | Luna `high` | Haiku `medium` | Hydrogen `medium` | Small 4 `high` |
| Writing / revision | Sol `high` | Sonnet `high` | Argon `high` | Large 4 `high` |
| Figure planning / style | Sol `medium` | Sonnet `medium` | Argon `medium` | Large 4 `medium` |
| R/ggplot2 and TikZ source | Sol `high` | Sonnet `high` | Argon `high` | Large 4 `high` |
| Figure critique / captions | Terra `medium` | Sonnet `medium` | Argon `medium` | Large 4 `medium` |
| Peer reviews / chair | Astra `high` | Opus `high` | Carbon `high` | Large 4 `high` |
| Formatting | Terra `medium` | Sonnet `medium` | Argon `medium` | Small 4 `high` |

Use lower effort for a cheaper initial evaluation if it still passes your domain
checks. Raise it for difficult methodology or figure-code failures; do not add
extra revisions beyond the original caps. Higher effort can increase latency
enough to hit the per-attempt timeout, which consumes an original retry. Model
and effort changes can change reviewer scores and accepted manuscripts. The
profiles do not enable OpenAI Ultra or any automatic team/delegation preset.

Mistral's levels are model-specific: Large 4 supports low/medium/high; Small 4
supports native high/none (Vibe calls none `off`). Mistral-hosted Z.ai
`zai-glm-5-3` and `zai-glm-5-3-flash` support low/high/max. GLM 5.3 is text-only;
Flash accepts images. The optional `mistral-glm.json` uses the text-only model for
literature synthesis and R/TikZ source, Large 4 for discovery, and Flash for
image/PDF roles. One live GLM discovery turn completed search but then attempted
a forbidden shell operation; it was stopped and remains a failed diagnostic.
The preset does not weaken that policy. It is an alternative
to evaluate, not a proven quality upgrade. The provider remains Mistral while the
model developer is Z.ai.

The installed Vibe 3.1 ACP interface accepts at most eight images per message and
10 MiB per image. Every PDF page is still retained and supplied; an invocation
exceeding the native limit fails explicitly, without truncation. Direct-image
Vibe calls require an explicitly supported multimodal model. Unknown aliases or
text-only models cannot silently use Vibe's separate vision-helper model.

## Evidence and limits

Each invocation retains `prompt.txt`, `request.json`, `transport.json`,
`response.txt` and native `events.jsonl`. ACP also retains both directions of
`acp-wire.jsonl`. The transport plan is hash-anchored to the request; auditors
recompute sessions, final text, completion, model/effort ACKs, media bytes and
search success from native records. They do not accept a self-declared normalized
receipt. Raw and effective manuscript results remain separate. Process/session
IDs are scoped by runtime, so equal ID strings from different providers do not
imply a shared conversation.

Provider API semantics, native system prompts, search, model weights, effort
budgets and internal agent execution differ. These adapters preserve the
controller structure, not identical model calls, scores or scientific quality.
See the current validation report for actual live execution versus labelled
protocol fixtures; the historical 57-session Codex run belongs to its original
frozen build.

Primary sources checked 15 November 2026:

- [Codex models and effort](https://learn.chatgpt.com/docs/models?surface=cli)
- [Claude Code CLI](https://code.claude.com/docs/en/cli-reference)
- [Antigravity models](https://antigravity.google/docs/models?hl=en) and [ACP](https://antigravity.google/docs/ide/extensions/acp/)
- [Vibe configuration](https://docs.mistral.ai/vibe/code/cli/configuration-reference) and [ACP integration](https://docs.mistral.ai/vibe/code/use-vibe-in-other-ides)
- [Mistral native reasoning levels](https://docs.mistral.ai/inference/conversations/reasoning)
- [Mistral-hosted GLM 5.3](https://docs.mistral.ai/models/zai-glm-5-3) and [GLM 5.3 Flash](https://docs.mistral.ai/models/zai-glm-5-3-flash)
