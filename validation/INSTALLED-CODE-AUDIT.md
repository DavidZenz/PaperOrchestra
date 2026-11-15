# Independent audit of the installed R/ggplot2 and TikZ build

**PASS for workflow execution and retained-source reproducibility, with the
scientific-output limitations below.** This audit inspected the completed real
run `validation/installed-r-tikz-e2e` and saved-source replay
`validation/installed-r-tikz-replay`. It did not edit the installed skill, source
package, run, replay, or manuscript.

## Exact build and execution evidence

The frozen 41-file bundle has SHA-256
`8eaf7371f56354cab08b016d6508f9745a696f83cdea8e88c7662d2dc4035039`.
I independently recomputed and compared the complete file maps and bundle digest
for the repository skill, installed skill, launch manifest, retained source
snapshot, finish manifest and currently installed skill. **All are identical.**
The exported ZIP also matches its freeze-record hash and contains exactly those
41 files. Unlike the earlier supplied-figure demonstration, this run executes
the final frozen installed implementation; no later implementation patch is
being substituted for its launch build.

The installed `summarize_trace.py` returns `evidence_valid: true`, no errors and
no warnings. I also checked the raw records independently rather than relying
only on that result:

| Check | Observed result |
| --- | --- |
| Actual agent execution | 65 starts, 65 process records, 65 distinct PIDs, 65 distinct session IDs and 65 completed turns. Every dispatch command is `codex exec --ephemeral`; none resumes/forks a prior conversation or invokes a fixture executable. Prompt/response hashes and raw session receipts all match. |
| Agent responsibilities | 1 probe, 1 outline, 21 literature discoveries, 1 literature synthesis, 1 section writer, 2 figure planners, 2 stylists, 4 R visualizers, 4 TikZ visualizers, 6 figure critics, 2 captioners, 12 peer reviewers, 4 chairs, 3 content editors and 1 formatting reviewer. |
| Parallel graph | Literature and plotting stage intervals overlap by approximately 559 seconds. Both receive the same outline hash produced by OutlineAgent. Discovery reaches 10 concurrent calls; total agent concurrency reaches 12. Section writing starts after both branches complete. |
| Live search | All 21 discovery calls contain concrete completed native or connected search-tool evidence. Raw JSONL parses using physical LF delimiters with no malformed records. |
| Artifact integrity | All 98 files in the completed manifest match their recorded hashes. The enriched outline, filled template and bibliography copies match; the section draft reaches refinement unchanged. |

Installed source verification against upstream
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56` passes: 20 locked bundled hashes,
22 original source files and seven original Gemini parser/retry function ASTs.
The retained `validation/code-rendering-tests.log` records **115 passing tests**
for this build. Test fixtures are separate from this real run.

## Generated figures and replay

The real figure pipeline retains eight successful renders: four R/ggplot2 and
four LaTeX/TikZ. Each code-generation call has its own Codex process/session and
figure context. Both figures run all three upstream critic rounds, regenerating
after each; neither stops with `No changes needed.` The final selection therefore
reflects the authors' round cap, not an assertion of unanimous visual approval.

The two selected authoritative sources are:

- `figure_sources/2d0b5e5b99364a3c85791d3e4bc0b610/source.R`
  (SHA-256 `279a7d4e7d20eb0a6abffb827f647ea3487b0c35e69e61975a2e4105a07dbaf4`).
- `figure_sources/ffbaa274ed3f459a9578874478418d16/source.tex`
  (SHA-256 `0e593c805cefd9d6ce898527f7009807405f913ce88197b51715f01f592cbfee`).

Their source bytes match actual visualizer responses. Their native PDFs,
previews, executable R wrapper and `render.json` are hash-anchored to the
completed run. Selected JPEGs match the plotting handoff and LaTeX copies, and
the section writer's input snapshot records those exact figure hashes.

The saved-source replay reports zero LLM calls and renders all eight retained
versions in fresh directories using local R or pdfLaTeX. I independently compared
source/wrapper bytes and original/replay JPEG bytes for every version: **all
match**. For both the original and replay of all eight versions, an independent
300-DPI rasterization of the actual native PDF produces the saved JPEG bytes.
This verifies PDF/preview correspondence, including the single-PDF export path.
The inspected frozen replay implementation has no model-dispatch path.

The recorded environment is Codex CLI 0.167.0, R 4.6.2, ggplot2 4.0.3 and
pdfTeX/TeX Live 2026. The retained experiment script and all four experiment
replay outputs also match their originals byte-for-byte: observations, metrics,
experimental log and R session information.

## Review, acceptance and stopping

Four complete reviewer ensembles each execute three sequential independent
reviewers followed by a separate chair. I recomputed every bounded integer
mean, including Python rounding: **all 36 saved numeric fields match**. Chair
non-numeric review fields remain intact. Overall is 3 for baseline and v1–v3.

| Candidate | Subaxis gain / drop | Observed upstream decision |
| --- | --- | --- |
| v1 | 1 / 0 | Accept neutral improvement; continue. |
| v2 | 0 / 0 | Accept neutral improvement; continue. |
| v3 | 0 / 0 | Accept neutral improvement; stop at the three-round cap. |

All three worklog decisions match an independent calculation from their saved
before/after scores. The final TeX and delivered five-page PDF are byte-identical
to accepted v3. Exactly one formatting review reports no issues for both figures
and the table; no formatting editor or formatting candidate follows it.
Rejection/reversion and failure-retry paths are covered by deterministic tests;
this installed run does not claim to have exercised those alternatives.

## Genuine limitations and manuscript caveat

- Semantic Scholar returned 114 HTTP 429 responses and one HTTP 200. The final
  verified citation map is empty. Successful live search is demonstrated;
  successful comprehensive literature retrieval is not. The manuscript adds no
  verified citation keys.
- PaperBanana reference files are absent. The log records the authors' empty
  few-shot fallback for both figures; no retrieval-agent invocation is fabricated.
- The synthetic five-observation calculation and Overall 3 scores are workflow
  evidence, not a publication-quality result or a claim of predictive
  generalization. Codex model/tool adaptations do not reproduce the authors'
  original model outputs numerically.
- **Embedded manuscript recipes are not authoritative figure provenance.** The
  reviser inserted `filecontents` recipes named `fig_intercept_error.R` and
  `fig_residual_workflow.tex`. Their hashes differ from every retained actual
  visualizer source. They are model-written supplementary reconstructions,
  whereas `figure_sources/` and the verified replay contain the exact code that
  produced the delivered images. No manual edit or additional iteration was
  applied to conceal this distinction.

No raster image model is required by the approved R/TikZ adaptation. The actual
run uses independent Codex code workers followed by native R and TeX tools.
The frozen implementation, real dispatch records and reproducible figure assets
support the workflow-conformance result; they do not by themselves establish
scientific validity of every sentence in the generated manuscript.
