# Intentional adaptations from upstream

Baseline: google-research/paper-orchestra commit
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56`. Exact source hashes and the four
vendored-source adjustments V001–V004 are in `../upstream-lock.json`.
These are implementation adaptations, not claims of identical model behavior.

Current user-approved rendering policy (15 November 2026): R/ggplot2 for data
plots and LaTeX/TikZ for scientific diagrams, with separate Codex workers and
retained source for every generated figure. This replaces the earlier request
for an image-generation-model adapter. The earlier supplied-figure run remains
historical evidence; the final code-rendering run must use the frozen installed
bundle and exercise the parallel plotting branch.

## Runtime and orchestration

| ID | Upstream | This skill | Consequence / validation |
| --- | --- | --- | --- |
| R001 | Gemini/OpenAI SDK inference requests | Fresh `codex exec --ephemeral --sandbox read-only` subprocess and independent session per model attempt | Actual separate agents; no resume/fork or shared conversation. Controller threads and joins are unchanged. CLI event logs and PID/session IDs prove execution. |
| R002 | Distinct upstream writer/reflection/discovery/image model names | Upstream names remain in controller and request metadata; text calls use Codex's configured model by default; optional explicit `--model` or `--model-map-json` | Model family, model weights and sampling behavior differ. This is workflow conformance, not replication of authors' numerical paper-quality results. No model is silently asserted to be Gemini. |
| R003 | `system_instruction` provider role; some outline/figure prompts already first text part | Labeled upstream system instruction inside the independent agent's task; original text parts kept in order | Codex host/developer/user instructions remain higher priority. Provider instruction hierarchy cannot be reproduced exactly by a CLI prompt. Wrapper adds per-invocation execution, input isolation, output-format and search-use instructions; R022 separately adds the user-approved selected-source provenance context for manuscript workers. |
| R004 | Provider Google Search grounding tool | Codex live `web_search` enabled only for discovery; completed native web-search or connected `codex_apps/search_service.web_run` tool event required | Search provider, ranking, citation metadata and tool semantics differ. No substitute internal-memory answer or text mention of a tool is accepted as tool execution. Semantic Scholar enrichment, title matching, dates, missing-abstract rejection, rates and no-retry behavior remain exact upstream. |
| R005 | Gemini temperature, response modalities, candidate settings | Original configs recorded; CLI has no equivalent supported temperature control | Temperature 0.1/0.4/0.75 etc. are provenance, not enforced sampling promises. Text response parsers and all original Gemini retry function bodies are copied exactly. |
| R006 | PDF byte input to Gemini; OpenAI path extracts text | Original PDF retained, text from every page added, every page rasterized at 1.5x and sent as `--image` | Input representation changes, no intentional page/text truncation. Raster figure inputs and upstream 2×2 formatting screenshot grids remain original. Tests check all pages and text reach child arguments. |
| R007 | Gemini image generation API | Earlier implementation exposed an optional external image executable | Superseded in the supported generated-figure entrypoint by user-approved TikZ rendering (R018). The historical low-level image transport remains for source compatibility/tests; no real image-model validation is claimed or required for the code-based mode. |
| R008 | CLI copies/removes existing output folders | Wrapper requires fresh/empty output and validates required files before the runtime probe | Avoids deleting earlier runs and paying for a probe with missing inputs. Authors' three whole-paper attempts and their within-run overwrite/copy behavior are unchanged. |
| R009 | SDK exceptions and provider retries | Original five-attempt Gemini retry/backoff/parser functions wrap Codex transport failures; per-process timeout defaults to 600s | An additional bounded process timeout can consume an original retry attempt. Discovery still retries empty/error outcomes three times, whole paper three times, content three rounds, formatting once. Backend transport/capability failures remain visible even if upstream catches them. |
| R010 | Missing tools may be swallowed in plotting/reviewer loops and still leave a PDF | Capability preflight, fatal ledger and unresolved search-task ledger make the manifest fail even if upstream returns success | A search attempt without a completed tool event can recover through original retries; only unresolved tasks fail the run. Image tool exhaustion after the original five attempts is recorded fatal even if upstream skips that figure. Deliberate fail-closed reporting change. Ordinary scientific review/compile exceptions retain upstream behavior. No agent impersonation fallback. |
| R011 | Mostly stdout and final controller artifacts; individual reviews transient before chair | Append-only JSONL trace, original prompt/response/config/media snapshots, raw child events, parsed response files, stage boundary hashes, HTTP status/hash, compilation and decision events | Additional audit artifacts do not replace the upstream formats. All three raw reviews and the chair are separately inspectable. API-key values/headers are not logged. Artifacts may contain the user's research materials. |
| R012 | Direct backend initialization requires provider credentials at import, including unused OpenAI dependency | No provider clients or API keys at import; `google-genai` is used only for existing content/config data types | Authenticated Codex supplies text execution. Import tests require no model credentials. Fully replaced `utils/llm_backend_utils.py` forwards to the same copied Gemini response parsers, including for configured Codex models. Upstream OpenAI-specific parser repair differences are not reproduced. |
| R013 | Matplotlib uses host cache defaults | Wrapper supplies writable run-local `MPLCONFIGDIR`/`XDG_CACHE_HOME` only if unset | Cache location only; plot code and styles unchanged. |
| R014 | Dataset and venue templates are caller resources; front-end/batch utilities also provided upstream | Skill provides single-paper driver, not Streamlit/email/batch-dataset UI; vendored batch functions remain but are outside supported entrypoint | Does not alter the within-paper graph. No dataset is implied to be bundled; user supplies materials and conference template. |
| R015 | README recommends Python 3.11 and unpinned dependencies | Wrapper supports Python 3.11+; actual validation environment versions recorded separately | Validated here on Python 3.15.2 and Codex CLI 0.167.0; no claim that all dependency versions or other platforms are tested. Existing upstream invalid-escape warnings are preserved. |
| R016 | Implicit namespace-package directories | Added small `__init__.py` files for bundled `methods`, subpackages, `utils` and `autoraters` | Prevents unrelated installed packages with generic names from shadowing the bundled controller. No original function or prompt changes. |
| R017 | Controller success is based on final-PDF existence | Wrapper additionally audits recorded separate-session evidence, original handoffs, sequential ensemble spans, parsed artifacts and final PDF hashes | A generated PDF with inconsistent/unprovable evidence is reported failed, not validated. A recorded mid-ensemble backend failure can still take upstream's zero-score/reversion fallback; it is reported separately from successful ensembles. A run with no complete ensemble cannot demonstrate the requested ensemble conformance. When a whole-paper retry replaces the refinement working directory, saved aggregate files are checked against that retained refinement span; earlier complete ensembles remain independently recorded in the trace. The observer does not change any controller acceptance/reversion decision. |
| R018 | Matplotlib code execution for plots; image-model raster generation for diagrams | Separate Codex code workers produce R/ggplot2 or standalone LaTeX/TikZ; real Rscript/pdflatex subprocesses render the saved code | User-approved renderer substitution. Only the visualizer task/code-output contract changes (A001/A002 below). Plan, style, critic, caption, figure pools, branch join and stopping remain the pinned controller. A render error returns upstream's `None` signal for the existing critic; no extra repair loop is added. |
| R019 | Plot code is transient; generated image bytes are primary | Retain every attempt's model-generated `.R`/`.tex`, deterministic export wrapper, native PDF, JPEG preview, source/input hashes, render command/log and R session metadata | Figure output must be source-backed and match an actual separate worker response. A fixed initial R seed 0 stabilizes random plotting primitives; numerical data invention remains forbidden. Each preview is rasterized from its one native PDF, preventing stochastic geoms from differing between separate exports. Source replay makes zero model calls and checks preview identity in the recorded environment. PDF timestamps may differ; no cross-platform byte identity is promised. |
| R020 | No complete installed-package immutability check | Snapshot/hash the entire installed skill before the first agent; rehash it before completion; audit the snapshot and start/end equality | The exact installed source bundle must stay unchanged through the full run. Cache bytecode is excluded. Output must be outside skill/material directories. This closes the earlier launch-versus-late-hardening validation limitation for new frozen runs. |
| R021 | Shared in-process Matplotlib state and image-provider rendering | Isolated Rscript (`--vanilla`) and pdflatex (`-no-shell-escape`) renderer processes with one bounded execution per attempt | Rendering process isolation and tool timeout are operational adaptations. Original figure concurrency remains five workers. Network/model retries remain the original five-attempt helper; figure repairs remain at most three critic rounds with the same exact stop string and last-valid-image retention. |
| R022 | Manuscript writers receive figure images/captions; no authoritative source manifest or consistency gate | At section-writing entry, after the unchanged parallel join, match each selected preview hash and figure ID to its successful render. Copy exact sources, R export wrapper, metadata, native PDF and preview into `figure_code/<figure_id>/`, publish `figure_provenance.json`, and pass the manifest plus exact source/wrapper text and file snapshots to section/content/format workers. Normalize their complete LaTeX results before the controller consumes them; retain original parser results and effective results separately. Compilation only verifies references/source hashes and snapshots the checked candidate. | User explicitly requested consistent exact-source references, not alternative recipes. A004 separately documents the manuscript appendix and replacement-recipe removal. The format editor's raw-response channel is normalized too because upstream consumes it directly. Empty/incomplete responses, JSON worklogs, number/order of model calls and all upstream scientific decisions/retries/stops remain unchanged. Audits recompute the transformation, verify each source/context/candidate/PDF handoff and fail on unprovable provenance. Historical runs without the version flag are explicitly outside these new checks. |

R022's manuscript gate verifies that every selected preview is actually embedded
in the final PDF, in addition to its visible source paths/checksums. Recipe
removal preserves ordinary function-name discussion, library setup, comments,
and caller template/style definitions; these are not replacement figure recipes.
The TikZ task explicitly names its pdfLaTeX engine and built-in font constraints;
the separate style-output adaptation A005 records the system-font substitution.

Stage/PDF/HTTP observer wrappers preserve their underlying return values and
scientific control decisions. The separate R022 manuscript adapter changes
effective LaTeX payloads before the controller consumes them, with original and
effective results retained. The full controller,
reviewer ensemble and numeric aggregation execute the pinned source, not a second
hand-reimplemented DAG. The three reviewers are intentionally sequential because
that is what upstream does. Literature discovery (10 workers), figure generation
(5 workers), and the literature/plot branch (2 workers) retain their actual pools.
Parallel generated matplotlib execution also retains upstream's shared-global
pyplot behavior; this port does not claim to repair its race risks.

Original retry functions retain their historical "Gemini API" console labels;
those labels do not identify the actual backend in this port. Request manifests,
process/session events and `run.json` identify the Codex transport. Provider error
messages emitted as structured failed-turn events are carried into exceptions so
the original nonretryable input/400 checks can still recognize them.
Malformed CLI JSONL records are retained verbatim and excluded from evidence;
the final auditor reports their invocation, line and hash as warnings. They cannot
satisfy session, completion or search-tool requirements. A run still needs valid
independent records for all required proofs. JSONL is split at physical LF only:
the real demonstration contained valid U+0085 characters inside search-result
JSON strings, which generic Unicode `splitlines()` incorrectly treats as record
boundaries. The corrected reader preserves those intact records.

## Historical image-tool contract

This contract describes the first implementation only. The supported generated
figure mode now uses R/TikZ code; its CLI cannot select the raster image backend.
No separate image model is needed for scientific diagrams under the user's
revised requirement.

`--image-command-json` is a JSON argv array, never shell text. The runtime appends
one path to a JSON file with `contents`, original `config`, `requested_model`, and
absolute `output_path`. The external tool must apply those prompts/configs using
an actual image generation capability and write a valid raster image at that
path. Its stdout/stderr are retained, exit status checked and raster decoded.
The tool executable itself is a configured dependency; this package does not
ship a provider-specific image-generation client or claim an image tool was used
in the supplied-figure demonstration. Validate a configured tool in its target
runtime before relying on generated diagrams. An implementation must document
any changes it makes to image model, style, aspect ratio or prompt semantics.

As upstream does, successful bytes are returned as base64 and ultimately written
under a `.jpg` filename, regardless of the original encoded raster type. The
runtime validates the image, not its filename suffix. Caption and critic handoffs
remain unchanged. PaperBanana examples/guides are external and not in the upstream
repository; absent assets use the original warning/empty-reference fallback.

## Scientific guidance, domain prompts and artifact formats

See [scientific-adaptations.md](scientific-adaptations.md) for the separate ledger.
There are **no edits** to scientific guidance, domain-specific planning/style/
review prompts, review rubrics, aggregation scales, revision output syntax, or
manuscript schemas. Visualizer task/output-language adaptations A001/A002 and
the user-approved provenance appendix A004 are separately recorded in that ledger.
Copied upstream prompt files remain
byte-identical; renderer hooks select the documented alternative task contract.
Transport input representations R003/R006 and added trace outputs R011 are
separately identified above. The original prompts' tensions are retained and
disclosed; preservation is not endorsement of their scientific advice.

## Demonstration-only choices

| ID | Category | Adaptation |
| --- | --- | --- |
| D001 | Domain/input fixture | Five-point deterministic affine residual calculation, actual results generated by `examples/tiny/make_materials.py`; synthetic workflow demonstration, no novelty/generalization claim. This replaces the unavailable authors' research dataset solely for the demonstration. |
| D002 | Output/template fixture | Supplied generic article template and 700–1000 word demonstration guidelines, not an original conference template. This is a caller input, not a rewrite of role output formats or upstream scientific prompts. |
| D003 | Optional branch selection | Real demonstration uses the upstream default supplied-figure path. Generated-figure parallel branch is covered by controlled controller tests; no real diagram-tool run is claimed. |
| D004 | Code-rendering demonstration input | A new finite R calculation supplies no figures and requests one numerical MSE plot and one residual-flow diagram. The normal outline/figure agents generate and critique both; it is a caller-input choice, not a prewritten outline or shortened search/revision rule. The earlier D003 supplied-figure run does not satisfy this new validation. |
| D005 | Requested correction of an existing manuscript | A separate output directory retains the historical accepted manuscript's scientific body and selected images, removes its two model-written replacement recipes and adds exact-source references/copies using A004. This is an explicitly requested deterministic correction, with zero model calls or new peer reviews, not a replay of the old workflow or an extra upstream revision. The original frozen run and its scores/artifacts remain intact. |

Validation fixtures use explicitly mocked model/tool responses to reach branch,
retry, stopping and aggregation cases deterministically. They are never presented
as real scientific experiments or real model calls. The separate real run retains
its own manifest, raw Codex session events and complete output tree.
