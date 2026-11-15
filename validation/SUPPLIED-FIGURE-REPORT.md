# PaperOrchestra Codex port validation

Baseline: [google-research/paper-orchestra at ca1b3fa01c2970fc7cda32d16245db38d57b3f56](https://github.com/google-research/paper-orchestra/tree/ca1b3fa01c2970fc7cda32d16245db38d57b3f56).
Validation date: 15 November 2026 (Europe/Vienna).

## Source conformance

`upstream-verification.json` records successful verification of 20 bundled source/
license hashes, 22 actual upstream Git blobs and working files at the pinned
commit, and AST equality of seven original Gemini parser/retry functions.
All controller/agent/reviewer files and scientific prompt modules are byte-exact.
The four small vendored utility edits are individually recorded in the source
lock; runtime and input/output transport adaptations have a separate register.

No scientific guidance, role-output schema, reviewer scale, aggregation,
acceptance, reversion or controller stopping rule was rewritten. The original
scientific prompts include problematic guidance and tensions that are explicitly
disclosed in `paper-orchestra/references/scientific-adaptations.md`.

## Deterministic execution evidence

`tests.log` records 84 passing tests of actual vendored controllers, runtime
transport and trace auditing. External model/tool/PDF effects are controlled
fixtures. Fixture subprocess tests prove process/session separation mechanics;
they are not real model calls.

`controlled-traces.json` contains durable controller traces for:

- Three reviewers, a separate chair, integer conversion, bounds, rounded means
  and retention of the chair's prose/decision.
- Both literature/plot branches reaching a synchronization barrier and joining
  before section writing; exact literature and draft artifact handoffs.
- Whole-paper retry recovery on attempt three and exhaustion after three.
- Score increase acceptance, later decrease reversion, tie degradation rejection,
  balanced tie acceptance and neutral continuation to the three-round cap.
- Compile failure consuming a round while the previous accepted draft remains
  context, empty output/exception stops, and one compile-gated formatting pass.
- A model parse failure recovering on its third independent attempt, using the
  original five-attempt loop/backoff. Raw labelled fixture transport artifacts
  are in `controlled-runtime/`.

The full suite additionally covers discovery deduplication and concurrent search,
sequential enrichment, missing abstracts, citation-key collisions, raster figure
handoffs, figure critic stopping/regeneration, nonretryable input errors, missing
capabilities, tool failures/timeouts, and forged or inconsistent execution traces.

Independent forward testing correctly refused a generated-figure request with no
image-tool executable. Independent audit identified tool-evidence and silent
failure gaps; regressions now reject search prose, failed native/connected tools,
orphaned results, reused sessions, overlapping reviewer spans, missing handoffs,
corrupted parsed outputs and an altered final PDF.

## Real end-to-end demonstration

The final real run completed under `real-e2e-final/`, with its controller stdout
in `real-e2e-final.log` and full audit in `real-trace-summary.json`.
The real execution uses fresh authenticated Codex CLI sessions, actual live
search, actual Semantic Scholar HTTP requests, supplied figure images, extracted
PDF context and real local `pdflatex`/`bibtex` compilation. No model response or
HTTP metadata is replaced with a fixture in this run.

Observed results:

| Evidence | Result |
| --- | --- |
| Model execution | 34 actual Codex process launches, 34 distinct sessions, 34 completed turns, no failed agent attempts |
| Literature | 15 separately invoked discovery agents with live search; 105 real Semantic Scholar requests: 95 HTTP 429 and 10 HTTP 200; two enriched papers retained by upstream filters |
| Manuscript handoffs | All four observed outline/template/bibliography/draft copy pairs have identical hashes |
| Reviews | Three full ensembles, each three sequential separate reviewers plus separate chair; all 27 numeric aggregate fields independently match upstream rounded means |
| Revision one | Overall 2 → 3, subscore gain 2/drop 0; accepted and continued |
| Revision two | Overall 3 → 3, gain 0/drop 1 in Clarity; rejected, reverted and stopped before round three |
| Formatting | Exactly one visual review; no issues reported, so no formatting editor or re-review invoked |
| Selected output | Final TeX and PDF byte-identical to accepted revision one; rejected revision two is retained as an artifact |
| PDF inspection | Four pages, one supplied figure, readable rendered text/table/chart, no observed clipping or overlap; no manual changes applied |
| Audit | `evidence_valid: true`, no errors or warnings |

`observed-revision-handoff.json` additionally checks the actual second revision's
accepted TeX/PDF, previous acceptance worklog, raw experiment log and citation map.
`pdf-checks.json` records selected-version byte equality and page/image counts.

The launch manifest pins its implementation hashes. Audit and failure-reporting
code was hardened during development while this run was active, and the final
auditor was applied afterward. The controller, prompts and scientific decision
code remained unchanged. The real run is evidence for the successful inference
path; deterministic tests cover the late failure/audit changes. The independent
review is in `INDEPENDENT-AUDIT.md`.

The initial audit reader mistakenly used Unicode `splitlines()` on JSONL, which
split U+0085 inside a valid search-result string. Physical-LF parsing proves all
records intact. Both runtime and audit readers are corrected, with regressions;
the original raw log was retained without alteration.

The raw materials are generated by `examples/tiny/make_materials.py`: five exact
synthetic points with a constant residual of three. Measured squared errors for
intercepts 0, 1.5 and 3 are 9, 2.25 and 0. This is a finite workflow demonstration,
not a scientific novelty/generalization claim. The generic short article template
and supplied-figure branch are separately documented demo adaptations D001–D003.

An earlier diagnostic run in `real-e2e/` was interrupted when its evidence check
failed to recognize successful connected-search events. It is explicitly marked
interrupted, retained with logs, and excluded from successful-run claims. The
corrected runtime accepts completed native web-search items or completed,
error-free calls to the connected search tool. It never accepts prose as proof.

## Practical limits

- Text inference uses Codex models/configuration rather than the original Gemini
  models. Provider sampling temperatures and exact system-role semantics are not
  reproduced; workflow conformance does not imply identical research outputs.
- Default runtime lacks an image synthesis executable. Generated diagrams require
  a configured real image-tool adapter. That branch is tested with controlled
  effects, not claimed as a real diagram-generation demonstration.
- Live search provider behavior and Semantic Scholar availability/rate limits can
  affect retrieved references. Original enrichment rejection/skip rules remain.
- Only the recorded environment is tested here (`environment.json`). This host
  required escalation to launch authenticated child Codex processes. A failed
  sandbox-only subprocess probe is a runtime limitation, not permission to replace
  the workflow with one agent.

Full artifacts contain the supplied research inputs and individual model outputs.
Keep the output tree to reproduce handoffs and compile the final TeX; the PDF by
itself does not contain its bibliography/style/figure source files.
