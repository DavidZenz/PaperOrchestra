# Dated model recommendations and publication

On 15 November 2026 the repository README gained recommendations for all eight
agent groups across OpenAI, Anthropic, Google Gemini and Mistral. Sources are
linked beside the recommendations. Antigravity is identified as an agent
platform with plan-dependent models and a distinct orchestration system.

The role assignments are engineering judgments inferred from official capability
descriptions. No PaperOrchestra cross-model benchmark, price/latency measurement
or manuscript-score equivalence is claimed. Only the Codex CLI transport is
implemented. Other provider columns need separate, validated execution adapters;
model-name routing alone does not supply credentials, protocols or tool support.

`paper-orchestra/profiles/openai-balanced.json` supplies explicit suggested
OpenAI IDs for all groups and the runtime probe. Users must choose this optional
profile; it does not change defaults or the user's reasoning configuration.
The intentional adaptation is R024. No controller, role implementation,
scientific/domain prompt, rendering implementation or manuscript output format
changed in this update.

Validation for this package is recorded in `model-recommendations-freeze.json`,
`model-recommendations-tests.log`, `model-recommendations-plan.json` and
`model-recommendations-source-verification.json`. The preview invokes no model;
it checks routing, not provider access. The existing model-policy tests cover
actual dispatch arguments, fixed selection across retries and audit checks.

All 183 tests passed in 23.938 seconds. The installed and source previews agree
on all 17 role slots with zero model calls. The installed validator passes;
comparison with actual upstream verifies 20 vendor hashes, 22 pinned source
files and all seven original parser/retry ASTs. The 46-file installed/source
bundle is `e7079804d00657127643212d0ffe638953440abe73a078a99b56f41426dae57f`;
the release archive is byte-checked against it. Only three skill instruction/
reference files and the new optional JSON profile changed from the preceding
45-file build; runtime/controller/rendering code is unchanged.

The prior 45-file model-policy build remains frozen in
`model-profiles-freeze.json` and its dated archive. The completed 57-session
paper run remains attached to bundle `735b4837…`, with its original full source
snapshot and archive. It does not validate this proposed mixed-model profile.
The corrected manuscript and its exact-source archive are unchanged.

Publication includes source, tests, fixtures, final full provenance execution,
saved-code replay, controlled trace evidence and historical reports/archives.
Earlier raw runs and interrupted diagnostics remain local and are excluded by
`.gitignore`; their reports clearly retain their historical scope. Artifact
bytes and recorded historical absolute paths are preserved.
Git line-ending conversion is disabled so cloned evidence retains its checksum
identity. Original upstream code, generated source and raw tool logs retain
their whitespace rather than being reformatted for publication.

Before pushing, a clean Git archive of the initial publication commit was
extracted to a separate temporary directory. All 888 exported files matched the
working files byte-for-byte. The suite discovered 183 tests and completed with
179 passing, four optional skips and no failures in 23.210 seconds. The skips
were the three actual-upstream-checkout checks and one older historical-run
check, because those optional local directories are excluded from Git. The
complete local suite and actual-upstream comparison passed separately above.
The clean export reused the existing Python dependency environment and native
R/TeX installations; it was not a fresh dependency-install test. See
`publication-checks.json` and `publish-export-tests.log` for the input commit,
tree hash, log hash and exact skip reasons. No new model calls were made.
