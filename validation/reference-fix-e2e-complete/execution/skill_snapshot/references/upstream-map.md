# Upstream execution contract

Source: [google-research/paper-orchestra at ca1b3fa01c2970fc7cda32d16245db38d57b3f56](https://github.com/google-research/paper-orchestra/tree/ca1b3fa01c2970fc7cda32d16245db38d57b3f56). Line numbers below refer to that original source, before the four operational vendor patches in [upstream-lock.json](../upstream-lock.json). All files in `vendor/methods/`, including scientific/domain prompts, and `vendor/autoraters/agent_review.py` are copied byte-for-byte. The Codex model/tool adapter is an adaptation documented outside this contract. This document describes observed implementation, including surprising behavior, rather than an idealized paper-writing process.

## Dependency graph and execution boundaries

```text
raw idea + experiment log + template + conference guidelines + cutoff
  -> OutlineAgent model invocation -> outline.json
      -> HybridLiteratureAgent branch:
           collect and deduplicate tasks
           -> discovery model invocation per task (pool 10)
           -> JOIN all discovery calls
           -> Semantic Scholar enrichment sequentially, 1 second/candidate
           -> bibliography -> citation map -> inject outline citation keys
           -> literature synthesis model invocation -> four literature artifacts
      -> PlottingAgent branch (only with use_plotting):
           per figure (pool 5):
             retriever invocation, when external reference pool exists
             -> planner invocation -> stylist invocation
             -> visualizer invocation -> render/execute generated code
             -> [critic invocation -> optional new visualizer/render] up to 3
             -> caption invocation -> figure and metadata
      -> JOIN literature and plotting branches (outer pool 2)
      -> copy literature outline/template/bibliography and figure artifacts
      -> SectionWritingAgent model invocation -> raw_draft_paper.tex
      -> compile baseline PDF -> extract text -> reviewer 1 -> reviewer 2 -> reviewer 3
      -> area-chair meta-review invocation -> deterministic numeric aggregation
      -> [revision invocation -> compile candidate -> reviewer ensemble -> chair
          -> numeric aggregation -> accept/revert/stop] up to 3 rounds
      -> format-review invocation on PDF grid images
      -> at most one formatting-editor invocation -> compile -> accept/revert
      -> final_refined_paper.tex + final_refined_paper.pdf -> final_paper.pdf
```

Each model-call boundary above must become a separate Codex invocation with its own input, output and identity trace. Deterministic collection, enrichment, file copying, score aggregation, compilation and stopping logic stay in Python. A single agent reciting these roles is not equivalent execution. The upstream reviewer ensemble is sequential, not parallel. Only the branches/pools explicitly shown run concurrently. Upstream also offers batch-paper `ProcessPoolExecutor` execution; this is independent of the per-paper DAG.

The no-plot entrypoint runs Outline -> Literature -> Sections -> Refinement sequentially and copies supplied raw-material figure files into `latex_writeup/figures` before its three-attempt loop. The plotting entrypoint runs literature and plotting concurrently after outline; both read the same initial `outline.json`. Only after both complete does it overwrite that outline with `literature_agent_output/outline_v1.json`. Sources: `methods/paper_writer.py:36-220`; `methods/paper_writer_with_plotting.py:35-298`.

## Role inputs, prompts and artifact handoffs

| Role / upstream boundary | Exact supplied context and responsibility | Output consumed downstream |
|---|---|---|
| Outline (`methods/agents/outline_agent.py:38-60`) | Formatted `outline_agent_system_prompt` with cutoff, idea text labeled `idea.md`, experiment log labeled `experimental_log.md`, original template labeled `template.tex`, guideline text. | JSON object saved as `outline.json`, with `plotting_plan`, `intro_related_work_plan`, `section_plan`. Downstream branches consume this object. |
| Literature task collector (`literature_review_agent.py:211-266`) | Intro `search_directions` with hook/gap context; related-work `limitation_search_queries` with mission/hypothesis context (fallback subsection title + methodology cluster); every section/subsection `citation_hints` with content-bullet context. | Tasks with `section`, `focus`, `context`, `search_type`. Exact duplicate identifier is `section:focus`, marked processed before submission. |
| Discovery (`literature_review_agent.py:305-324,426-475`) | Targeted prompt includes exact hint, context, cutoff, primary-original-paper requirement and `DiscoveryResult` schema. Exploration includes focus, context, broader gap, cutoff, 10–15 relevant/influential-paper request and schema. Google Search tool. | `candidates`: title, year, reason. Targeted asks exactly one candidate. Hardcoded `gemini-3-flash-preview`; temperature 0.1 targeted / 0.4 exploration. |
| Metadata enrichment (`literature_review_agent.py:326-424`, `utils/scholar_utils.py:34-100`) | Candidate title/year/reason, originating task section, cutoff, Semantic Scholar API key if configured. Search limit 3, requested title/authors/venue/year/abstract/citationCount/journal/publicationDate; fuzzy title ratio +10 for matching hinted year, select highest if >70. | `PaperData` registry keyed by normalized title. Abstract required and truncated to 1500 characters plus marker. First section association wins. No fabricated fallback metadata. |
| Literature assets (`literature_review_agent.py:132-140,268-303,507-594`) | Enriched papers. Bibliography resolves citation-key collisions before map/injection. Key = cleaned first-author surname + year (fallback 2024) + first two non-stopword title words; colliding keys suffix a, b, etc. | `references.bib`; `citation_map.json` containing key/title/authors/venue/year/abstract; `outline_v1.json` with section-associated `citation_candidates`, deleting section-plan citation hints. |
| Literature writer (`literature_review_agent.py:477-505`, `methods/prompts/literature_review_agent.py`) | System prompt formatted with count, floor(0.9 × count) minimum citations, cutoff. User instruction plus JSON payload: original template, updated Intro/RW plan, idea, experiment log, keys, complete enriched-paper objects. Loaded guidelines are not included in this payload. | Full updated template with Introduction and Related Work filled; other sections/preamble preserved, only collected papers cited; fenced LaTeX parsed into `updated_template.tex`. |
| Section writer (`section_writing_agent.py:81-218`, `methods/prompts/section_writing_agent.py`) | Updated outline/template; idea; experiment log; guidelines; formatted reference library (first 3 authors + et al., year, full abstract); figure list with filenames/captions. Existing raster figure images attached; PDF figure files remain available by filename but are not attached as images. Temperature 0.7. | Full compilable LaTeX in fenced block, extracted to `latex_writeup/raw_draft_paper.tex`. Fill missing sections, derive tables from log, insert all supplied figures, preserve filled Intro/RW. |
| Initial refinement baseline (`content_refinement_agent.py:201-246`) | Raw draft copied into refinement working directory with template assets, bibliography and figures; experimental log, citation map and guidelines retained by path. | `initial_draft.tex`, compiled `initial_draft.pdf`, PDF grid screenshots and `peer_reviews/review_v0.json`. Baseline sets current accepted TeX/PDF/review and initial/current Overall. |
| Reviewer 1/2/3 (`autoraters/agent_review.py:112-181`) | Identical extracted full PDF text; exact `AGENTREVIEW_INSTRUCTIONS`; default knowledgeable/responsible/benign persona and Overall rubric; temperature 0.75. Three independent calls in sequence. | Each returns JSON review with prose, seven 1–4 subaxes, Overall 1–10, Confidence 1–5, boolean Ethical Concerns and Accept/Reject Decision. Reviewer's brief public assessment preface is upstream output format; private reasoning need not be solicited by a port. Any change to that request is an output/prompt adaptation. |
| Area chair (`autoraters/agent_review.py:184-211`) | Same review-format instructions plus all three reviewer JSON objects, labeled Review i/n; experienced inclusive-area-chair system prompt formatted with reviewer count; temperature 0.75. | Meta-review in same format. `None` falls back to first reviewer object. Deterministic numerical aggregation then overwrites numeric fields. |
| Content reviser (`content_refinement_agent.py:249-305`, `methods/prompts/content_refinement_agent.py`) | Current accepted PDF bytes, iteration number, entire previous iteration worklog, current aggregated reviewer feedback and score, guidelines, experiment log as data truth, citation map as reference truth, current accepted full TeX, exact refinement system prompt. | JSON worklog first, then full fenced LaTeX. Parser returns JSON-string wrapper with `json` and `latex`. Candidate `refined_paper_vN.tex/.pdf`, screenshot grids, `peer_reviews/review_vN.json`; acceptance metrics/worklog persisted. |
| Format reviewer (`content_refinement_agent.py:111-177`) | Current accepted PDF rendered as page grid images, supplied conference guidelines, exact inline prompt. Must report every figure/table plus other layout issues, only guideline-supported defects. | JSON `figure_and_tables` keyed by object with detected_issue/suggested_fix, plus `other_issues`. Review error returns `{"Error": ...}`. |
| Format editor (`content_refinement_agent.py:499-577`) | Formatting review, guidelines and accepted full TeX; inline instruction limits edits to formatting/layout/spacing except explicit feedback allowance. | Fenced full LaTeX, `formatted_candidate_v1.tex/.pdf`; if PDF exists, accepted without peer re-review. Format worklog records outcome and feedback. |

The shared `utils/prompt_utils.py:15-43` isolation/anonymity prompt is appended to Outline, literature-writing, section-writing and content-revision scientific prompts. It permits only current supplied materials and logical reasoning, forbids external remembered facts or author identity inference, and says it overrides other instructions. Discovery has its own external-search prompt and is not given that appendix.

## Plotting subgraph details

`methods/agents/plotting_agent.py:31-201,215-274` uses a pool of five figure jobs and collects results in completion order. A failed figure job is logged and omitted rather than failing the whole branch.

Per figure, normalize `plot_type` to plot/diagram (unrecognized strings containing plot/chart select plot, all others diagram); visual intent combines title + objective. Raw material selection iterates `.md` files matching data-source text; if no match, reads `experimental_log.md` and `idea_sparse.md` when present. Therefore `data_source="both"` triggers the fallback and custom idea filenames may be omitted. Aspect ratio defaults to 16:9. The model calls in `utils/paper_banana_utils.py` are:

1. Retriever (`335-398`): target raw content + visual intent and PaperBanana candidate pool metadata; exact plot/diagram retriever prompt selects top ten IDs. Plot pool unlimited, diagram pool first 200. Missing `ref.json` returns empty examples without a model call. Retrieval uses repaired JSON and drops unknown IDs.
2. Planner (`468-532`): plot/diagram planner prompt, retrieved example content/intent and actual reference images where found, current raw content + intent. Outputs detailed description as plain text.
3. Stylist (`535-574`): plot/diagram stylist prompt, detailed description, external `neurips2025_{plot|diagram}_style_guide.md` if present, raw content + intent. Outputs refined detailed description. Missing style file becomes empty text.
4. Visualizer (`647-682`): plots receive plot visualizer prompt + styled description, return Python code; local `execute_plot_code_worker` executes it with an initially empty globals dictionary (generated code must import its own dependencies), then saves the active matplotlib figure as JPEG base64. Diagrams receive diagram visualizer prompt + description and aspect ratio through image-generation backend, returning raster base64. Code execution is a required tool boundary; it is not simulated by the author agent.
5. Critic (`577-644`): plot/diagram critic prompt, current image if available (otherwise explicit generation-failure notice), current description, raw content + intent. Repaired JSON contains `critic_suggestions`, `revised_description`; invalid JSON defaults to `No changes needed.`. If revised description equals that string, keep old description. Outer loop stops only when suggestions stripped equal **exactly** `No changes needed.`; otherwise update description and regenerate image. Up to configured 3 rounds; critic exception breaks; empty regenerated image keeps previous image while description remains updated.
6. Caption (`401-465`): final description + raw content + intent and image if base64 length >100, temperature 0.5, plain text caption without Figure/Caption numbering or Markdown. Prefix cleanup follows.

Saved `plotting_results.json` contains figure_id/title/task_name/description/caption/aspect_ratio/critic_history and image_path when image saving succeeds; base64 is removed. Figure files are `figures/{lowercase_space_replaced_id}.jpg`. Outer writer copies these figures into the LaTeX project and writes `figures/info.json` entries `{name, caption}`. Literature outputs are copied only after both branches finish.

External PaperBanana data/style resources are not part of upstream repository. The V003 path override permits supplying them; it does not change missing-resource behavior or prompts. The pinned diagram visualizer uses an image backend; the user-approved current adapter substitutes real TikZ rendering (R018/A002). Report unavailable capabilities explicitly rather than manufacturing output or substituting a text checklist.

The user-approved exact-source handoff R022/A004 extends manuscript inputs after
this join. The adapter resolves selected preview bytes to the successful render,
publishes `figure_provenance.json` and exact `figure_code/<figure_id>/` copies,
and supplies them to section/content/format workers. It assembles a visible
source appendix in complete LaTeX results before upstream saves or scores them.
Raw responses and effective artifacts are distinct records. Compile observers
verify and snapshot the candidate; acceptance/reversion still select the same
effective TeX/PDF pair under the unchanged controller rules.

## Reviewer aggregation

`autoraters/agent_review.py:149-170` iterates Originality, Quality, Clarity, Significance, Soundness, Presentation, Contribution, Overall, Confidence. For each reviewer value:

- Convert with Python `int(value)` (floats truncate; invalid strings/None rejected by ValueError/TypeError).
- Retain only values within that field's limits (1–4; Overall 1–10; Confidence 1–5).
- If at least one valid score exists, assign `int(round(np.mean(valid_scores)))` into chair/fallback review. This uses nearest rounding with ties-to-even, not floor or always-round-up.
- If no valid scores exist, leave chair/fallback field unchanged. Decision and prose remain meta-review output and are not recomputed from Overall.

There are no persona differences, majority vote, confidence weighting or reviewer communication. Reviewers receive paper text, not source log, citation map or guidelines. The three reviewer calls are sequential and the chair runs only after all three return. Exceptions can escape aggregation if a reviewer object is malformed (for example None); ContentRefinementAgent catches the review error and substitutes Overall 0.

## Revision, reversion and stopping

`content_refinement_agent.py:248-442` limits content revision to three rounds. The actual logic is:

| Candidate result | Accepted-state transition | Stop behavior |
|---|---|---|
| Empty parsed LaTeX | Keep previous TeX/PDF/review | Break content loop |
| Failed candidate compilation (no PDF) | Keep previous TeX/PDF/review; no candidate review | Consume this round, continue |
| Overall increases | Accept candidate TeX/PDF/review/score | Continue remaining rounds |
| Overall decreases | Reject candidate; retain previous accepted state | Break and revert |
| Overall ties, summed absolute negative subaxis deltas > summed positive deltas | Reject candidate; retain previous accepted state | Break and revert |
| Overall ties, gain >= drop (including all-zero deltas) | Accept candidate TeX/PDF/review/score | Continue remaining rounds |
| Revision/parse/compile/screenshot/other exception | Retain last accepted state | Break content loop |

Comparison axes are the seven 1–4 subaxes; Overall and Confidence are excluded from gain/drop. Missing extracted scores default to zero; float conversion catches ValueError but not TypeError. Each scored candidate logs round, returned agent plan, before/after scores, per-axis deltas, total gain/drop and one exact outcome: `ACCEPTED_SCORE_INCREASE`, `REJECTED_SCORE_DECREASE`, `REJECTED_DEGRADATION`, `ACCEPTED_NEUTRAL_IMPROVEMENT`. Candidate files and peer reviews remain on disk after rejection; final output points to the last accepted version.

Then run one formatting iteration (`max_formatting_loops=1`), even after content rejection. Detect issue strings case-insensitively against `none` in figure/table entries or other-issue entries. No issues -> skip editor. Format-review exception produces only Error; current issue detector treats that as no detected issues. Formatting candidate is accepted solely on PDF existence, otherwise rejected; errors are logged and final accepted state retained. Outcomes: `ACCEPTED_COMPILE_SUCCESS`, `REJECTED_COMPILE_FAILURE`. There is no formatting score gate and the final reported peer Overall is from the content stage. Final accepted TeX and PDF become `final_refined_paper.tex/.pdf`; writer copies the latter to `final_paper.pdf`.

## Retry and compiler semantics

- Model wrapper: `utils/gemini_utils.py:138-224` defaults to five attempts for generation/parse errors. Before attempts 2–5 delays are 0, 5, 10, 20 seconds. Error text containing maximum-token/400-bad-request/400-invalid-argument patterns immediately rethrows. Parsed-None checking is enabled by default. This is nested inside discovery's three attempts and writer's three full-pipeline attempts.
- Discovery: up to three calls per task for empty/error results; final `[]` is not a whole-pipeline failure. Discovery futures can fail independently. Tasks are not re-added after failure during that literature run.
- S2: one request per candidate, 5-second timeout, no retry; non-200/no results/low-match/error returns None. There is a 1-second delay before every candidate enrichment request.
- Full paper: `max_n_tries=3`; any exception reruns from outline. Template is copied at each attempt. Literature and outline outputs are overwritten; refinement workdir is removed/recreated before refinement. Original initialization cleans LaTeX output/final PDF once before this loop; attempts do not all start with a clean output directory. Success returns True, exhaustion False.
- Compilation: `utils/pdf_utils.py:169-250` removes existing candidate PDF, clears five TEX-related environment variables, runs pdflatex -> bibtex -> pdflatex -> pdflatex, each with 30-second timeout, collecting logs. It accepts PDF existence provided no command timed out, even if individual commands return nonzero. No model repair call is inserted by this helper. Content/format stages test file existence.
- PDF reading first tries PyMuPDF and falls back to pypdf if extracted text <100 characters or extraction raises. Screenshots are 2x2 page grids at scale 2.0, padded with white images.

Date filtering has two upstream layers: S2 requires publicationDate strictly before first day of cutoff month, with year-only same-year allowed only after January; literature's subsequent filter allows unknown dates and dates through the default first cutoff day. Both layers are retained. Registry and output ordering can depend on discovery completion order and set iteration.

## Preserved quirks and scientific/domain prompt tensions

No scientific guidance, output format or domain prompt is changed in vendored code. Separate operational vendor deviations are V001 (suppress API-key print), V002 (remove unused Gemini client import) V003 (optional external PaperBanana path), and V004 (remove unused pymupdf4llm import). `paper_writer_with_plotting.py:51-52` already initializes time_log/Start_Time_Absolute in the pinned source; no alleged initialization fix was made.

- Refinement scientific prompt `methods/prompts/content_refinement_agent.py:83` says **Never explicitly state a limitation**. It also says ignore requests for new experiments/data absent from log (`:44`). A different research-writing policy must be documented as a scientific-guidance adaptation.
- Section prompt demands detailed ablations/qualitative analysis (`section_writing_agent.py:53`) while forbidding hallucinated numbers (`:42`); no extra missing-data policy is silently inserted.
- Section prompt says fill missing author names (`:35`); appended shared isolation/anonymity prompt explicitly forbids author identity inference/metadata and declares precedence. The isolation appendix is preserved as authored.
- Literature writer is instructed to cite floor(90%) of collected papers, use only supplied keys, treat post-cutoff papers as concurrent and not claim superiority over papers absent from experimental comparisons. Discovery's top-tier/high-citation filtering is domain guidance, not a runtime necessity.
- Outline scientific guidance is explicitly top-tier ML-conference oriented, asks 3–5 intro queries, 2–4 related-work clusters and citation hints for every external dependency. PaperBanana styling names NeurIPS 2025. Supporting other disciplines or shortening search for a demonstration is a domain/input adaptation that must be recorded separately.
- Prompt output fences and schemas are retained. The JSON+LaTeX parser returns a JSON string wrapper; malformed worklog JSON becomes an error object while a missing LaTeX block becomes None. It does not enforce proposed response schemas beyond parsing.
- Reviewer analysis preface is an upstream request for reasoning. A runtime may provide concise assessment rationale only; document that response-style adaptation without altering score schema or aggregation.
- Plot code execution uses Python `exec` in the orchestrator process and module-global matplotlib pyplot; multiple figure threads share plotting state. Additional isolation is an operational execution adaptation, not an upstream scientific change.
- Missing paper dataset, missing external PaperBanana benchmark/style assets, unavailable search/API, unavailable image backend, unavailable separate agents, or missing LaTeX/PDF tools are runtime limitations; distinguish them from a completed end-to-end execution.
