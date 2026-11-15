# Independent mixed-runtime end-to-end audit

**PASS for recorded execution conformance and artifact provenance, with a retained diagram layout defect.** The [run manifest](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/run.json) is `completed`. I inspected raw native records and independently recomputed counts, reviewer means, decisions, hashes, source selection, and final-file lineage. A fresh invocation of the installed trace auditor reports valid evidence with no errors or warnings; this assessment does not rely only on the saved `execution/audit.json`. This audit made no model calls and changed only this report.

The [frozen 57-file bundle](/Users/davidzenz/PaperOrchestra/validation/multiruntime-freeze.json) is `b770c9165b8fbba1b371c39115d9cb51de2f7740a1d11e9b145fc20423ff9a05`. Launch, finish, implementation map, retained `execution/skill_snapshot`, current source, installed skill, and archived ZIP file maps all match it. The ZIP checksum matches its freeze. All **118** completed-run artifact checksums match actual files.

| Worker backend | Separate processes/sessions | Native completed attempts | Failed attempts |
| --- | ---: | ---: | ---: |
| Codex | 11 | 11 | 0 |
| Claude Code | 18 | 18 | 0 |
| Antigravity | 29 | 29 | 0 |
| Mistral Vibe | 7 | 6 | 1 |
| Total | **65** | **64** | **1** |

All 65 process IDs and backend-scoped native session IDs are distinct. Requests equal trace starts; launch commands equal retained plans; prompt, plan, image and successful-response hashes match. Native final messages equal retained responses. Every selection agrees with the [resolved model policy](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/execution/model_profile.json), including separate content/format routing. The 62 upstream role calls complete; the additional attempts are one runtime probe and two retries. These are native executable launches, without mock executors or labelled protocol servers.

The [raw trace](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/execution/trace.jsonl) shows literature and plotting branches overlapping by **508.097 seconds**, both joined before section writing. The two figure branches overlap by **89.565 seconds**. Enriched outline, template and bibliography handoffs match their literature outputs; the section draft enters refinement unchanged. Each of the 22 discovery attempts contains completed native search evidence.

Two original model-call retries recover without changing backend, model, effort, role or prompt bytes:

- Discovery call `c96d0d30655140b1b975a5bc8179ca0f`: Antigravity / `gemini-3.8-flash` / medium. The first native turn completes, but the original JSON parser returns `None`; the second fresh process/session produces a parsed dictionary. Both retain prompt SHA256 `40ee4ebb…`.
- TikZ call `43f3ad06182b4917a21e93a060b71fbd`: Vibe / `zai-glm-5-3` / high. Attempt `df9c67df…` reports a forbidden tool and aborts; fresh attempt `64aa97cf…` completes with code. Both retain prompt SHA256 `3fbb2db1…`. The failed native attempt is retained, not disguised as successful output. These recoveries use the original five-attempt helper; no backend substitution or extra retry loop occurred.

There are **four complete ensembles**, each three sequential, separate Claude peers followed by a separate Codex chair. Their call spans do not overlap. Each ensemble's peer prompts are identical, and its chair receives all three exact parsed reviews. I recomputed **36 numeric fields** directly from the peers using upstream integer conversion, axis bounds and rounded means; all equal the saved reviews. The chair's proposed numeric values do not replace these means. Axis order below is Originality, Quality, Clarity, Significance, Soundness, Presentation, Contribution, Overall, Confidence:

| Review | Recomputed nine-axis vector | Content decision |
| --- | --- | --- |
| Baseline | `1,2,3,1,3,3,1,2,4` | Initial Overall 2 |
| v1 | `1,2,3,1,3,3,2,3,4` | Accepted Overall increase to 3; gain 1, drop 0 |
| v2 | `1,2,3,1,3,3,2,3,4` | Accepted neutral tie; gain 0, drop 0 |
| v3 | `1,2,3,1,3,3,2,3,4` | Accepted neutral tie; gain 0, drop 0; three-round cap reached |

The [content worklog](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/content_refinement_workdir/content_refinement_worklog.json) matches these independently derived decisions. No v4 editor or ensemble occurs. **This run exercises cap stopping, not real content reversion.** Reversion and other failure/stopping cases remain separate evidence in the [controlled conformance tests](/Users/davidzenz/PaperOrchestra/tests/test_upstream_conformance.py) and [earlier frozen `735b…` real-run audit](/Users/davidzenz/PaperOrchestra/validation/MANUSCRIPT-PROVENANCE-AUDIT.md).

Formatting executes one Claude review, one Claude format editor, and one candidate compilation. The [format worklog](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/content_refinement_workdir/format_refinement_worklog.json) records `ACCEPTED_COMPILE_SUCCESS`. There is no second formatting review or peer ensemble afterward. Compilation success therefore does not establish that every reported visual issue was resolved.

All **five** manuscript handoffs—section, three content revisions, and the native Claude format editor—contain the exact selected-source manifest and all ten selected artifact copies. Each raw native response equals its upstream snapshot, passes the original parser, and reproduces the recorded effective result under the declared provenance transformation. The first three need canonical-reference normalization; v3 and formatting are already canonical and remain unchanged. No replacement figure recipe is retained. All five compile snapshots match the corresponding effective TeX and exact source copies before compilation; there is no late manuscript rewrite.

All six renderer inputs equal code extracted from their actual visualizer responses, including the failed input; metadata, wrappers and sources remain anchored in `run.artifacts`. Five renders succeed. The [selection manifest](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/figure_provenance.json) resolves selected JPEG hashes to the actual successful sources:

- R plot: second render `264922fd…`, source SHA256 `189339846a19ff9afe13e24a7efe95cc4a83ec38a9778113caa8f8c92dd0589a`, preview `4908fc60…`.
- TikZ diagram: third successful render `b874cf3b…`, source SHA256 `4e19b72bbe6333b3602153f3eab1b16ae392856ffa6a5527ea378e37911eb5fe`, preview `771b22f2…`. The subsequent fourth render `1d4d3165…` fails with `Missing \endgroup inserted`; the upstream controller retains the previous valid image and its actual previous code.

Root, writing-workspace, refinement-workspace, worker-context and compile-snapshot copies all match those selected originals. The [saved-code replay](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final-replay/replay.json) uses zero model calls. I checked its actual files: all five successful-render sources and replay previews equal the original bytes, including both selected figures.

The final six-page [PDF](/Users/davidzenz/PaperOrchestra/validation/multiruntime-e2e-final/final_paper.pdf), refinement final PDF and formatted candidate are byte-identical: SHA256 `2d5dcf41d3d9bce764a3b9d6699078f8f909dd1bff68898b2508ac94437e22e6`. Final TeX equals the formatted candidate: SHA256 `a8787097d12ea93d8e3444cac0de82d1c61fc3ba19af7200af0f3bb8434edd60`; its formatting input equals accepted v3. Independent PDF extraction finds both exact selected JPEG bytes and copyable source paths/checksums in every complete candidate and the final PDF.

Material limits remain. I viewed the selected diagram and confirmed overlapping evaluation-box/callout text. Both the figure critic and formatting reviewer reported it; the last diagram repair failed, and the preserved stopping rules retain the imperfect earlier image. No manual repair or extra iteration was applied. Semantic Scholar records **138 HTTP 429 and three HTTP 200 responses**, with an empty verified citation map; bibliography quality is consequently not demonstrated. Missing PaperBanana examples take the upstream empty-example fallback. Codex/Claude CLI arguments prove requested effort; they do not echo an effective level. ACP acknowledges native model/effort, which does not establish equivalent provider compute or model weights. This small synthetic demonstration establishes orchestration and provenance, not scientific publication quality or every possible failure branch.

The earlier GLM **component discovery failure** belongs to the separate native-check build `9f7e…`, described in [NATIVE-CAPABILITY-AUDIT.md](/Users/davidzenz/PaperOrchestra/validation/NATIVE-CAPABILITY-AUDIT.md). It is not included in this run's counts or presented as a successful discovery. This completed paper run belongs to frozen build `b770…` throughout.
