# PaperOrchestra upstream equivalence audit

The current skill is a faithful port of the authors’ **single-paper workflow**.
It executes their original controller, including the same agent stages,
handoffs, reviewer ensemble, scoring and revision decisions. Runtime
substitutions and stricter acceptance checks can change the resulting paper.
The evidence establishes workflow equivalence, with the differences below.

## Comparison scope

On 23 November 2026, the audit compared commit `19ce683` and the 61-file
installed bundle `061e40d7…` with the original pinned upstream commit
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56`. The source, archive, installed
skill and snapshot from the completed run matched. Source verification passed
for all 20 locked vendored files, 22 original source files and seven preserved
Gemini parser and retry functions. All 330 tests passed again in 42.250 seconds.
This audit reran the code checks and inspected the recorded live run. It made
no new model calls. [Pinned upstream](https://github.com/google-research/paper-orchestra/tree/ca1b3fa01c2970fc7cda32d16245db38d57b3f56) ·
[Frozen installation](revision-bibtex-freeze.json) ·
[Live run checks](revision-bibtex-e2e-checks.json)

Upstream `main` at `d9bae997e793a015ed38bb1605be9eb58c00284f` was six
commits ahead of the pin, including three merge commits. The changes cover
lazy Gemini and OpenAI client setup, missing dependencies, and three LaTeX
escape fixes in two prompt files. They do not change the controller graph,
score aggregation or revision rules. Those newer upstream files are outside
our byte-preservation claim. [Upstream comparison](https://github.com/google-research/paper-orchestra/compare/ca1b3fa01c2970fc7cda32d16245db38d57b3f56...d9bae997e793a015ed38bb1605be9eb58c00284f)

## What matches and what differs

| Area | Audit finding |
|---|---|
| Stages, dependencies and handoffs | The same controller creates the outline, runs literature and plotting concurrently when selected, joins both branches before section writing, then compiles, reviews, revises and formats. The original supplied-figure path is also retained. The latest run verifies the plotting path of this exact bundle. |
| Agent responsibilities and interfaces | Separate native sessions execute the original role boundaries. The locked scientific and domain prompt files and main response formats match the pin. Runtime prompt additions include input isolation, source provenance, verified BibTeX and the formatting scope. There is an extra capability probe before the original workflow. |
| Review, scoring and stopping | Three independent sequential peer reviews and a separate chair run for each scored draft. The original bounded integer means, rounding, increase and tie rules, reversion and stopping logic are used. The three content rounds, one formatting pass, and original model, discovery and whole-paper retry budgets remain. Error handling can reach a different branch because runtime checks are stricter. |
| Models and tools | Native Codex, Claude Code, Antigravity and Mistral Vibe workers replace SDK calls. The original temperatures are retained as evidence rather than enforced on those backends. Search uses the worker's native tool and must leave evidence. Revision PDFs can be delivered as extracted text and page images. Crossref and OpenAlex supplement Semantic Scholar, so the retrieved library can differ. |
| Figures and provenance | R/ggplot2 and TikZ replace Matplotlib and model-generated diagram pixels. Figure planning, critique, reselection and captions stay in the original workflow. The skill saves exact figure sources and adds their provenance to the manuscript. Source replay verifies render reproducibility in the recorded environment. |
| Bibliography and formatting eligibility | Upstream can proceed with an empty library and largely relies on PDF creation for compilation success. The skill requires a verified, nonempty BibTeX library and resolved citations. It can restore a recognized trailing inline bibliography to the established style and database. Formatting may change only supported layout options. These checks can reject a PDF that upstream would accept. |
| Repository scope and results | The skill targets the single-paper workflow. Upstream's Streamlit interface and batch entrypoints are outside the parity claim. There is no matched evaluation using the original model and tool combination, so manuscript quality, reviewer scores and benchmark results remain unverified for equivalence. |

The trace auditor independently recovered 60 separate process launches and
60 unique sessions, with 18 completed native searches and 458.7 seconds of
literature and plotting overlap. It verified four ensembles and all 36
aggregate scores. Two substantive revisions compiled and were accepted. A
third compiled and was reverted after a tied overall score with a declining
review criterion. The last accepted source entered formatting, which changed
only float placement. All six successful figure attempts replayed to identical
previews without model calls. [Recomputed trace](revision-bibtex-e2e/execution/audit.json) ·
[Saved-source replay](revision-bibtex-e2e-replay/replay.json)

## Citation coverage

Upstream asks the **literature synthesis** worker to cite at least
`int(0.9 * paper_count)` collected papers. That instruction is retained. The
run's literature template cited 62 keys from 69 collected records, meeting the
requested minimum. The initial full draft cited 64. Neither controller imposes
that minimum on the final revised draft. The content editor shortened Related
Work after reviewers flagged the broad survey and kept five cited works. The
69-record database remained intact. All five citations resolved and formatting
preserved them. The review still found gaps in offset modeling and least
absolute deviations. BibTeX and the aggregate score establish compilation and
selection, while adequacy of citation support remains a separate question.
[Original literature prompt](https://github.com/google-research/paper-orchestra/blob/ca1b3fa01c2970fc7cda32d16245db38d57b3f56/methods/prompts/literature_review_agent.py) ·
[Revision 2 review](revision-bibtex-e2e/content_refinement_workdir/peer_reviews/review_v2.json)

The deviation ledger has one documentation defect. It reuses R027 and R028
for native runtime behavior and also for bibliography behavior. The scientific
ledger's overview should distinguish byte-identical copied prompt files from
the runtime instructions and acceptance checks documented in R030, R032, A007
and A008. This audit did not alter the installed bundle.
