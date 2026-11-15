# Native worker runtimes and effort

The installed skill now dispatches fresh Codex, Claude Code, Antigravity and
Mistral Vibe workers through their actual native interfaces. Schema-2 profiles
select backend/model/effort per group or role; schema-1 model settings remain
compatible. The original controller, scientific role prompts and parser/retry
function bodies remain pinned. Intentional adaptations R025–R029 document the
transport, native settings, isolation, receipts and media limits separately from
the existing scientific/output adaptations.

## Package and controlled validation

The final 57-file source/installed bundle is
`b770c9165b8fbba1b371c39115d9cb51de2f7740a1d11e9b145fc20423ff9a05`.
Its [freeze](multiruntime-freeze.json) anchors the complete file map and portable
archive. [294 tests passed](multiruntime-tests.log) in 27.503 seconds. They use
labelled fixtures for deterministic control-flow coverage; they are not model
evaluation results. Native protocol tests launch real fixture subprocesses and
check session identity, direct media, completion/error handling, requested/native
model and effort, search IDs, duplicate RPC rejection, original retries,
manuscript handoffs and tamper detection. The original aggregation/reversion/
stopping and parallel-join tests remain in the suite.

[Actual upstream verification](multiruntime-source-verification.json) checks
20 vendor hashes, 22 source files and seven original parser/retry ASTs against
the pinned Git checkout. The installed validator and installed source comparison
also pass. No native client SDK is vendored: the ACP transport uses the native
CLI and a retained standard JSON-RPC exchange.

## Real native component checks

The [independent raw-evidence audit](NATIVE-CAPABILITY-AUDIT.md) verifies 12 real
processes and 12 unique backend-qualified sessions, with 11 successful components
and one failed GLM discovery turn:

| Runtime/model | Effort | Proven live checks |
| --- | --- | --- |
| Claude Code / `claude-haiku-5-5` | medium requested in native argv | Text, exact image input/read, completed WebSearch and parsed paper lookup |
| Antigravity / `gemini-3.8-flash` | medium, acknowledged | Text, exact image input/read, completed native search and parsed paper lookup |
| Mistral Vibe / `mistral-large-4` | high, acknowledged | Text, exact image input/read, completed native connector search and parsed paper lookup |
| Mistral Vibe / `zai-glm-5-3` | high, acknowledged | Text; discovery searched successfully then attempted forbidden shell and failed |
| Mistral Vibe / `zai-glm-5-3-flash` | low, acknowledged | Exact image input/read |

The image fixture is a retained R/ggplot2 source with bars 7,11,3. All four image
workers received its exact bytes and returned bar B=11 through the original
JSON parser. These are bounded component diagnostics with one direct attempt
per check, not shortened replacements for a paper run's retry rules.

GLM's failed discovery is retained without relabeling: native search returned
ten sources, then the worker attempted `bash` to parse its tool-result JSON file.
The adapter stopped that unsupported operation; no final response/end_turn was
accepted. The optional GLM starter profile consequently uses Large 4 for
discovery, base GLM for text-only synthesis/R/TikZ source, and Flash for images.
No shell permission, hidden vision model or automatic provider fallback was added.

These native checks belong to the 57-file build `9f7e6524…`, whose full
[freeze](multiruntime-native-check-freeze.json) and archive are retained. The
final `b770c916…` build changes only that optional GLM profile and two references;
all script/vendor bytes are identical. The distinction is explicit rather than
reassigning component evidence to another bundle.

Earlier native smoke/diagnostic runs remain local. They exposed stale pre-ACK
Antigravity notifications, its payloadless native search-completion shape, Vibe's
published connector/catalog names, and a component harness incorrectly requiring
unfenced JSON instead of using the original parser. Fixes have controlled
regressions. Initial failed manifests were not rewritten as successes.

## Mixed-provider full workflow

The final installed bundle completed the unchanged parallel plotting workflow
against the finite R/TikZ fixture, exit 0, `run.status=completed`, installed
source unchanged. The [standalone trace audit](multiruntime-e2e-final-trace-summary.json)
reports no errors or warnings. The exact input profile is
[mixed-runtime-fixture.json](mixed-runtime-fixture.json). It deliberately uses
account-available Haiku/Gemini 3.8 models for bounded validation, rather than
claiming to benchmark the suggested Opus/Carbon quality profile.

| Runtime | Fresh worker launches | Successful native completions |
| --- | --- | --- |
| Codex | 11 | 11 |
| Claude Code | 18 | 18 |
| Antigravity | 29 | 29 |
| Mistral Vibe / hosted GLM 5.3 | 7 | 6 |
| Total | 65 | 64 |

All 65 attempts have distinct native sessions, including the failed Vibe turn;
the built-in summary's 64 unique-session count covers successful completions.
The run lasted 1812.49 seconds. Literature and plotting overlapped for 508.10
seconds; discovery reached the original ten-worker pool. There were 21 logical
discovery calls and 22 native discovery completions: one response failed the
original JSON parser and succeeded on the original retry. A TikZ worker also
attempted a forbidden tool, then succeeded in a fresh worker through the same
original retry helper. Both retries retained prompt/backend/model/effort; no
new retry loop or permission was added.

Four complete ensembles each ran three sequential independent Claude peers and
a separate Codex chair. All 36 bounded integer means match the original Python
aggregation. Baseline Overall was 2; v1 rose to 3 and was accepted. Versions v2
and v3 remained 3 with zero gain/drop on the seven tie-break axes and were
accepted. The controller stopped at its original three-revision cap. One
formatting reviewer/editor pass was accepted on successful compilation, with no
additional scientific review. This run did not exercise reversion; controlled
tests and the historical frozen `735b4837…` run retain that separate evidence.

Five manuscript raw/effective result pairs and five compile snapshots retain
exact selected-source inputs throughout section writing, three revisions and
format editing. Seven saved PDF paths (five candidates and final copies) all
visibly contain the exact source paths/checksums and embed both selected JPEG
bytes; see [PDF/source checks](multiruntime-e2e-final-pdf-checks.json). The
[independent full audit](MULTIRUNTIME-E2E-AUDIT.md) rederives native/controller
and artifact evidence. All 118 non-execution artifact hashes match the manifest.

R/ggplot2 generated two successful attempts. TikZ generated four render attempts,
three successful and one failing with `Missing \\endgroup inserted`; the original
critic/failure path handled it within the existing cap. The failed fourth TikZ
render left the previous valid third render selected;
the manuscript references that third render's exact source, not the later failed
attempt. All five successful
source attempts replayed to identical previews with
[zero model calls](multiruntime-e2e-final-replay/replay.json). The selected
sources and the six-page manuscript are also bundled in the
[18-file source project](../dist/mixed-native-manuscript.zip).

The literature filter accepted no enriched papers: Semantic Scholar returned
138 HTTP 429 and three HTTP 200 responses. The bibliography is consequently
empty. This is a synthetic teaching-note workflow demonstration, not novel
research or a paper-quality evaluation.

**Observed visual limit:** read-only Poppler review of all six final pages found
an overlap between Figure 1's evaluation-box text and nearby annotation on page
3. The upstream formatting feedback also identified overlap; compile success
does not prove it was visually repaired. The exact selected image and its source
are retained unchanged. Other body text and the source appendix are readable.
Control-flow/provenance conformance and exact figure replay pass; publication
quality is not asserted.

## Clean publication export

A clean Git archive of implementation commit `4279ca4d5ce042c4077e7d7d4d591080f4e027e2`
was extracted to a separate directory. All 2087 exported files matched the
working files byte-for-byte. The exported suite discovered 294 tests: 290 passed
and four optional checks skipped, with no failures, in 25.604 seconds. The skips
are three actual-upstream-checkout tests and one older historical-run check;
those excluded development directories were present for the complete 294-test
workspace run. The clean export reused the existing Python dependency
environment and R/TeX installations; it is not a fresh dependency-install claim.

The exported standalone auditor also independently accepted the relocated full
mixed run with zero errors/warnings. No models were invoked for these checks.
See [publication receipts](native-publication-checks.json),
[test log](publish-native-export-tests.log), and
[relocated audit](publish-native-export-audit.json) for the exact source tree,
hashes, environment and skip reasons.

## Limits

Model recommendations remain engineering judgments, not cross-provider quality,
price, latency or score equivalence. Account access to every suggested model
has not been established. Codex/Claude retain requested effort flags but do not
echo observed effort in the inspected completion event; those fields remain null.
Antigravity's search evidence is native named/query-matched completion status,
without a retained search-result body. Vibe 3.1 limits a message to eight images
and 10 MiB each. Base GLM 5.3 is text-only; image jobs do not silently use a
different vision helper. Native API/tool loops and internal HTTP retries differ
from the original Gemini SDK while the controller's retry/stopping rules remain
unchanged.

Each runtime uses its own existing authentication and applicable subscription or
credits; the skill neither transfers entitlements nor silently substitutes an
account/model after a limit. Current official billing links and model/effort
guidance are in the README and [native runtime guide](../paper-orchestra/references/native-runtimes.md).
The README now prominently credits Yiwen Song, Yale Song, Tomas Pfister and
Jinsung Yoon and includes the citation provided by the pinned upstream project.
