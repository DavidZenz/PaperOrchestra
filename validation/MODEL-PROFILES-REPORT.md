# Invocation-time agent model selection

The installed skill now captures child-model preferences before a paper run when
none were supplied. It offers the current Codex CLI default for all roles,
assignments by agent type, or a saved JSON profile. Supplied choices/profiles are
used without another confirmation. Dispatched role workers do not restart this
setup conversation.

The [selection guide](../paper-orchestra/references/model-selection.md) documents
eight type groups, individual role overrides and precedence. R/ggplot2 and TikZ
workers, the three peer reviewers, separate meta-review, and content/format
editors can use distinct model assignments. Each peer remains a separate call;
model selection does not merge roles or change upstream control flow.

## Validation

- [183 tests passed](model-profiles-tests.log): 160 previous regressions plus
  23 new model-policy tests. The new tests use labelled fixtures, not live model
  results. They check actual runtime argv and handoffs, selection precedence,
  explicit null resets, all original retries retaining the selected model,
  distinct content/format routing, malformed configuration failing before a
  probe, coherent source/resolved snapshots, and audit rejection of model/argv
  or profile tampering.
- The [installed zero-call preview](model-profile-plan.json) demonstrates separate
  writer, content editor, format editor, peer and chair assignments. Its
  `*-fixture` IDs are deliberately illustrative; this validates routing, not
  access to those names. No provider or paid model call was made.
- An independent skill forward-check read the installed instructions and
  confirmed that missing preferences produce the setup question before any
  runtime probe. An explicitly supplied valid profile proceeds without repeating
  that question. No actual user question or model run was launched in this test.
- [Installed upstream verification](model-profiles-installed-source-verification.json)
  still passes 20 bundled hashes, 22 pinned source files and seven original
  parser/retry ASTs. The installed skill validator also passes.

The original [45-file model-policy freeze](model-profiles-freeze.json) has bundle SHA256
`2675e483b46d22b28ae2d507e4b2f17070622010dfd88f3307202f2524d0203f`.
Workspace source, installed skill and portable archive matched at that freeze.
The later [model recommendations](MODEL-RECOMMENDATIONS-REPORT.md) identify the
current documentation/profile package separately. Model-policy
snapshots and per-attempt `--model` arguments are checked by the runtime auditor.
Unknown/unavailable models are not silently replaced; actual service access and
image/search compatibility must be established when the chosen models execute.

## Scope and historical execution evidence

This update adds model configuration and the requested preference conversation.
It makes no scientific-prompt or manuscript-format change, and preserves the
original graph, parallelism, responsibilities, three-reviewer/chair ensemble,
aggregation, retries, acceptance/reversion and stopping. The intentional runtime
adaptation is recorded separately as R023.

No new manuscript run was requested or started while implementing model setup.
The prior [57-session full workflow](MANUSCRIPT-PROVENANCE-REPORT.md) remains
evidence for frozen bundle `735b4837…`, not an end-to-end execution of this new
optional model-policy build. Its exact archive is retained at
`dist/paper-orchestra-provenance-735b4837.zip`. The corrected manuscript and its
R/TikZ source project are unchanged. A future paper invocation will capture the
user's model choices and record actual execution of that profile.
