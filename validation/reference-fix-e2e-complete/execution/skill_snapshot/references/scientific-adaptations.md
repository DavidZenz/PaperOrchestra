# Scientific, domain and output-format adaptations

Pinned upstream: [google-research/paper-orchestra ca1b3fa01c2970fc7cda32d16245db38d57b3f56](https://github.com/google-research/paper-orchestra/tree/ca1b3fa01c2970fc7cda32d16245db38d57b3f56). See [upstream-map.md](upstream-map.md) for the observed execution contract and [../upstream-lock.json](../upstream-lock.json) for original/adapted file hashes.

## Current adaptation ledger

| Category | Intentional change in the reusable skill |
|---|---|
| Scientific guidance | None. Upstream scientific instructions remain present, including demands and tensions discussed below. |
| Domain-specific prompts | None. Top-tier machine-learning conference, canonical academic-literature search and NeurIPS 2025 visual-style framing remain as authored. |
| Scientific manuscript formats / response schemas | Outline JSON, candidate discovery objects, bibliography/citation-map formats, full manuscript LaTeX, revision worklog, review fields, plot metadata and caption outputs retain upstream schemas. Visualizer code/output substitutions A001/A002 and the visible exact-source manuscript appendix A004 are recorded separately below. |
| Model and tool transport | Codex invocation, system-instruction serialization, PDF/image delivery and backend/tool capability handling are runtime adaptations. Their actual implementation and limitations belong in [adaptations.md](adaptations.md), not in a claim that scientific prompts were rewritten. |
| Runtime dependencies / resource locations | V001–V004 in the lock remove API-key printing, an unused Gemini-client import, an unused pymupdf4llm import, and permit a PaperBanana resource-directory environment override. They do not modify scientific prompt strings or artifact formats. |

All files under `vendor/methods/`, `vendor/autoraters/agent_review.py`, and `vendor/utils/prompt_utils.py` are copied byte-for-byte. `vendor/utils/paper_banana_utils.py` has only its two recorded import/resource-location edits; its plot/diagram prompts are unchanged. `vendor/utils/pdf_utils.py` only removes an unused import. This is source-preservation evidence, not proof that a different model or transport produces identical content.

## User-approved visualizer task and code-output substitutions

These changes are implemented in `vendor/orchestra_visuals.py`, not by silently
editing the copied prompt modules. They apply only to the final visualizer task;
retrieval, planning, styling, numerical fidelity, critique and caption prompts
remain original. The same Codex model can serve different roles, but each role's
model call is a fresh independent worker invocation.

| ID | Upstream task/output | Active replacement and rationale | Scientific/acceptance effect |
| --- | --- | --- | --- |
| A001 | `generate_figure_visuals(task_name="plot")` requests Python/Matplotlib code | Request base R/ggplot2 code defining plot object `p`; preserve it as `source.R`, execute in Rscript and export a vector PDF and JPEG preview with a retained wrapper. Explicit user preference for R and reproducible source. | Code language and output contract change; raw data, visual intent, planning/style/critic prompts and manuscript handoff bytes remain the same kinds of inputs/outputs. A render failure still returns `None` to the original critic. |
| A002 | Diagram visualizer requests raster pixels from an image model | Request a complete standalone LaTeX/TikZ document, retain `source.tex`, compile with pdflatex, keep vector PDF and render its JPEG preview. User explicitly chose code-based diagrams and no separate image model. | Rendering tool and intermediate output format change. Scientific content/labels come from the original planned/styled description. Critic still sees the rendered image, uses the same JSON fields and stopping string, and captioning is unchanged. |
| A003 | Generated code/pixels can be transient | Require editable source plus checksums, command and tool-version metadata; support no-model replay. Numerical plot code uses fixed seed 0 and only supplied data. | Reproducibility artifacts are added; no new scientific measurements or manuscript schemas are introduced. Final audit rejects a selected figure without matching worker-produced source. |
| A004 | Writers/revisers can independently reconstruct supplementary figure recipes from images; source links are not required | Provide selected-worker source/wrapper artifacts, checksums and stable relative paths to manuscript workers. Deterministically maintain a visible, unnumbered Figure source provenance appendix on a new page, linking each figure to its exact source, SHA256, R wrapper and renderer/session metadata. Remove embedded figure-rendering recipes (`filecontents`, plotting/TikZ listings); preserve unrelated arithmetic, algorithm discussion and JSON worklogs. | Explicit user-authorized input/output-format adaptation, implemented outside copied scientific prompts. Effective complete LaTeX is assembled before initial/content/format candidates are consumed, compiled or reviewed, so accepted/reverted source and reviewed PDF remain consistent. Original raw responses/parser results and effective artifacts are separately traceable. This changes manuscript provenance content/layout; it does not change scientific guidance, numerical results, reviewer rubrics, aggregation or acceptance/stopping rules. |

A004 preserves ordinary function-name discussion, package setup, caller
template/style definitions and data-only scripts. Its recipe guard is scoped to
embedded rendering code; it does not prohibit discussing ggplot2 or configuring
TikZ. The final audit also verifies the selected image bytes inside the PDF.

**A005 — TikZ engine/font compatibility:** The visualizer task explicitly names
the actual pdfLaTeX renderer and requires built-in TeX serif/sans/mono families,
without `fontspec`, system fonts or XeLaTeX/LuaLaTeX dependencies. This is a
rendering/style-output constraint: an upstream stylist's requested system font
is approximated by a compatible TeX family. Scientific content/labels and the
stylist/critic prompts and stopping rules stay unchanged. An initial real TikZ
attempt in the interrupted provenance development run failed because it chose
`fontspec`; the source/error are retained. The explicit task constraint aligns
generated code with the existing toolchain and reproducibility environment.

The exact alternative task strings live in the adapter source and are included
in the frozen installed-skill snapshot and each actual request. They require
base R/ggplot2, built-in font families, plot object `p`, or a one-page standalone
TikZ document without external images. These are rendering/output constraints,
not changes to the scientific argument. Native vector PDFs and code are retained;
the upstream manuscript/critic/caption handoff continues to use JPEG previews.

Input selection for any demonstration is a separate experiment choice. A toy dataset, short requested paper or small user-supplied scope must be recorded in that run's inputs/manifest. Lowering required search breadth, silently deleting upstream prompt demands, removing a branch, inventing literature or treating a mock as a real agent is not an implicit demo exemption.

## Preserved output contracts

| Boundary | Upstream output requirement retained |
|---|---|
| Outline | One JSON object with `plotting_plan`, `intro_related_work_plan`, `section_plan`; upstream nested fields and plan constraints remain. |
| Discovery | JSON object following `DiscoveryResult`: `section_name`, `candidates`; each candidate has `title`, `year`, `reason`. Targeted asks exactly one candidate, exploratory asks 10–15 relevant candidates without forcing irrelevant results. |
| Literature writer | Full updated template in a `latex` code fence; fill only Introduction and Related Work, retain the rest. |
| Section writer | Full completed LaTeX in a `latex` code fence, with existing content and preamble constraints. |
| Content reviser | **Two code blocks in order:** JSON worklog then full LaTeX. Worklog fields `addressed_weaknesses`, `integrated_answers`, `actions_taken`; parser wrapper has `json` and `latex`. No replacement with a summary, diff, patch or prose checklist. |
| Peer reviewer / area chair | Review JSON retains Summary, Strengths, Weaknesses, Originality, Quality, Clarity, Significance, Questions, Limitations, Ethical Concerns, Soundness, Presentation, Contribution, Overall, Confidence, Decision. Numerical field ranges and Accept/Reject-only Decision remain. Numerical aggregation is deterministic upstream code, not a chair decision. |
| Format reviewer | JSON `figure_and_tables` mapping each figure/table to `detected_issue` / `suggested_fix`, plus `other_issues`; no invented scoring gate. |
| Format editor | Full revised LaTeX only in a `latex` fence; format-only instruction and compile-success acceptance remain. |
| Figure retriever | JSON top-ten IDs using `top10_plots` or `top10_diagrams`. |
| Figure planner / stylist | Detailed description text, retaining quantitative plot coordinates, visual intent and supplied stylistic instructions. |
| Plot visualizer | A001 substitutes R/ggplot2 code with retained source and vector PDF; the JPEG/base64 boundary remains. |
| Diagram visualizer | A002 substitutes editable standalone TikZ code, native PDF and JPEG preview for the raster image model; requested aspect ratio remains a task input. |
| Figure critic | JSON `critic_suggestions` and `revised_description`; exact `No changes needed.` stop string retained. |
| Caption | Plain text caption, without Figure/Caption numbering prefix or Markdown. |

The reviewer instruction also requests a `THOUGHT` preface before `REVIEW JSON`. A backend can provide a concise public assessment rationale; it must not solicit or expose private chain-of-thought. Any response-style handling of that preface belongs in the runtime adaptation record. The review JSON schema and numeric aggregation do not change with that handling.

## Candid upstream guidance tensions

These are preserved instructions, not added recommendations:

1. **Suppressing limitations.** `methods/prompts/content_refinement_agent.py:83` instructs the reviser never explicitly to state a limitation. The section writer calls limitations/future work nice to have (`section_writing_agent.py:54`), and the reviewer schema asks for limitations and potential societal impacts (`autoraters/agent_review.py:99`). These instructions can pull the manuscript in different directions. The port does not silently replace the reviser's demand with a different scientific-reporting policy.
2. **Missing experiments.** Refinement explicitly ignores reviewer requests for new experiments, ablations or baselines absent from the experiment log (`content_refinement_agent.py:44`), while every other reviewer question should be addressed through presentation changes (`:83`). Section writing always asks for detailed ablations and qualitative analysis (`section_writing_agent.py:53`) while prohibiting invented numbers (`:42`). The workflow must preserve supplied-data truth; it does not create missing measurements merely to satisfy a writing demand.
3. **Identity conflict.** Section writing says fill missing author names (`section_writing_agent.py:35`), but the appended universal isolation prompt forbids inferring or inserting author identities/affiliations and explicitly declares priority over other instructions (`utils/prompt_utils.py:27-41`). The appended anonymity rule is preserved. No author identity may be fabricated as a port convenience.
4. **Knowledge isolation.** The universal appendix says to write as though no prior knowledge exists, use only supplied materials and logical deductions, and avoid recalling an existing paper. A language-model backend cannot prove it has excluded every learned fact. The enforceable handoff is the supplied artifacts; the port should not claim a guarantee beyond the observed prompt/input contract. External literature discovered by the dedicated search branch becomes supplied context for downstream writing.
5. **Citation breadth and quotas.** The outline asks for 3–5 Introduction directions, 2–4 related-work clusters and canonical hints for every dataset/optimizer/metric/architecture dependency. Exploration asks for 10–15 relevant high-impact papers per task. Literature synthesis demands at least `int(0.9 * paper_count)` collected papers cited. These can be excessive for a toy topic or a small supplied log; they remain upstream scientific/domain guidance unless a separately recorded adaptation explicitly changes them.
6. **Evaluation claims.** The outline and literature writer restrict claimed superiority to comparisons present in the experiment log and constrain research chronology. Preserve those constraints. The source's operational date filters have subtle first-day/year-fallback behavior described in the execution map; prompt prose does not change their implementation.
7. **Venue and aesthetic specificity.** Outline, writers and reviewers explicitly target top-tier ML venues. PaperBanana styling names NeurIPS 2025 and can consume external benchmark/style files. Supporting another scientific discipline, format, citation convention or aesthetic requires a domain-specific adaptation entry. Missing external style files remain empty inputs under upstream behavior.
8. **Literal source quirks.** Some upstream Python prompt literals contain invalid escape-sequence warnings or interpreted escape characters. Source bytes are retained rather than silently cleaned up. Prompt repairs would need separate disclosure because they can change what the model receives.

If future scientific or domain changes are made, append a distinct entry with source prompt/location, original requirement, replacement, rationale, affected output/acceptance semantics, and validation. Do not mix that entry with model identity, dependency fixes or PDF transport. An execution trace proves dispatch and artifact flow; it does not establish manuscript correctness or scientific validity by itself.


## A005 — required bibliography (16 November 2026)

The user explicitly requires failure when the bibliography is empty. All
supported paper runs must retain a nonempty verified reference library, actual
citations using permitted keys and a resolved reference list visible in the PDF.
This is an output-readiness adaptation; copied domain prompts, review rubric,
score aggregation and scientific claims are unchanged. No citations are inserted
by a deterministic repair or invented by a fallback agent. R027's additional
metadata providers are a separate execution-environment substitution. R028
rejects bibliography-invalid candidates through the original compile-failure
path and checks the final accepted manuscript before declaring completion.


## A006 — literal metadata escaping

The BibTeX adapter escapes unescaped literal `&`, `%`, `#` and `_` in generated
metadata field lines (title, authors, venue, volume, pages). The upstream key
collision mutations and raw verified citation map are retained. This is a
serialization correction for provider-deposited text, not a replacement title,
new scientific guidance or a change to citation selection. Unsupported TeX
metadata still fails compilation/readiness; no invented replacement is inserted.
