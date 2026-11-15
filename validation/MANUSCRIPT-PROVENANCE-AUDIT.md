# Independent manuscript source-provenance audit

**Historical requested correction: PASS. Fresh full pipeline: PASS.**
The two results are separate: the historical correction makes no claim of new
agent execution or peer review. The completed fresh run at
`validation/provenance-e2e-final` supplies the real agent, review and in-pipeline
source-provenance evidence audited below. No implementation, run, replay or
manuscript files were edited during this independent audit.

## Requested correction of the historical manuscript

Audited `output/pdf/manuscript/` against its parent real run,
`validation/installed-r-tikz-e2e`. Its recorded correction adapter is build
`3db6fc620c05a54ff9d6f7c8ab0464fd027b44b6000a6ee865507dda7cf27679`.
Its `source_correction.json` explicitly records zero new LLM calls and zero
new peer-review calls. This is a requested derivative correction, not a newly
reviewed research result.

I subsequently checked that the final `735b4837...` adapter produces exactly the
same corrected historical TeX. The correction record distinguishes its original
adapter from this later validation. Its corrected TeX/PDF bytes remain unchanged.

I independently checked the actual files and rendered PDF:

- Applying the frozen normalizer to the parent's accepted TeX with the selected
  provenance manifest produces the corrected TeX **exactly**. It removes the
  two alternative figure recipes, `fig_intercept_error.R` and
  `fig_residual_workflow.tex`, and inserts the canonical source-reference block.
  The scientific manuscript body, excluding that new provenance block, is
  unchanged.
- The corrected PDF has six pages. Its first five pages are pixel-identical to
  the parent's five-page PDF at 1.5× rasterization. Both figure image files are
  also byte-identical to the parent's selected images. The additional sixth
  page presents the provenance references; I visually inspected it and found
  the source paths and checksums readable without clipping.
- Both published sources match code extracted from actual parent-run visualizer
  responses. Every published source, export wrapper, renderer metadata file,
  native PDF, preview and retained session-information file is byte-identical
  to the selected renderer's original artifact. The copies are not
  reconstructed approximations.
- PDF text extraction round-trips the exact source paths and SHA-256 values,
  the R export-wrapper path and checksum, and the metadata paths, with
  underscores intact. The manifest filename is also present. This checks the
  real PDF rather than merely inspecting TeX spelling.
- The corrected TeX and PDF hashes match `source_correction.json`, and the
  frozen provenance validator accepts the manuscript and its published files.

The authoritative source references are:

| Figure | Published exact source | SHA-256 |
| --- | --- | --- |
| Intercept error plot | `figure_code/fig_intercept_error/source.R` | `279a7d4e7d20eb0a6abffb827f647ea3487b0c35e69e61975a2e4105a07dbaf4` |
| Residual workflow diagram | `figure_code/fig_residual_workflow/source.tex` | `0e593c805cefd9d6ce898527f7009807405f913ce88197b51715f01f592cbfee` |

The R wrapper is `figure_code/fig_intercept_error/worker.R`, SHA-256
`6cb2b07327277f63fafbb553cd4f1f12c0f85bec37a49f3fa765da16a26b58ba`.
`figure_provenance.json` records all selected-artifact checksums.

The native-tool replay at `validation/published-source-replay` reports zero
LLM calls. I compared its actual files: both figures' source/wrapper inputs and
JPEG preview bytes are identical to the published authoritative copies. This
supports source/render reproducibility; it does not provide new peer-review
approval of the derivative appendix.

## Frozen build and tests

`validation/manuscript-provenance-freeze.json` records a 43-file installed
bundle with SHA-256
`735b4837fe9a5a8a521af16cc19634a55297e8297679e517addcbfd24d027026`.
I checked that the recorded test-log hash matches the actual log, which reports
**160 tests passed**. Those tests cover source selection, exact publication,
normalization before section/content/format consumption, actual upstream
controller acceptance/reversion/stopping, tampering, and real-PDF path/hash
round trips. The final build also narrows the graphics guard to preserve
legitimate TikZ setup and `ggplot()` prose, verifies selected JPEG bytes embedded
in the final PDF, and records the pdfLaTeX engine/font constraint as A005.
Mocked test responses are not presented as real agent execution.

## Interrupted diagnostic and fresh full pipeline

The earlier `validation/provenance-e2e` run is an **interrupted development
diagnostic**, not a completed conformance run. Its manifest records interruption
after forward checks exposed an overbroad guard that rejected legitimate TikZ
setup and `ggplot()` prose. Its original `3db6fc...` build, freeze and test
evidence were retained; the process was interrupted before changing that build.
This does not invalidate the separately verified historical derivative, whose
scientific body, figures and corrected PDF were not edited by that diagnostic.

**PASS:** `validation/provenance-e2e-final/run.json` is `completed`, with
`skill_unchanged: true`. The installed in-process and standalone audits report
valid evidence, no errors and no warnings. I independently checked the raw
records, deterministic transformations and actual artifact bytes, rather than
accepting those summary flags alone.

### Frozen build and actual separate execution

The complete 43-file maps for repository source, installed skill, launch
manifest, retained skill snapshot, finish manifest and current installation all
equal the final freeze, SHA-256
`735b4837fe9a5a8a521af16cc19634a55297e8297679e517addcbfd24d027026`.
The skill ZIP's hash and every archived file also match the freeze. All 122
completed-run artifact hashes match their actual files. Installed source
verification passes against upstream commit
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56`: 20 bundled hashes, 22 original source
files and seven original parser/retry function ASTs.

There are **57 actual Codex process launches, 57 distinct PIDs and 57 unique
completed sessions**. Every dispatch is a fresh `codex exec --ephemeral`, with
no resume/fork or fixture executable. All raw session, prompt and response
receipts match; raw JSONL contains no malformed records and no model-attempt
failure. This real run is distinct from the mocked tests.

The roles comprise one probe, one outline, 18 literature discoveries, one
literature synthesis, one section writer, two figure planners, two stylists,
four R visualizers, four TikZ visualizers, six figure critics, two captioners,
nine peer reviewers, three chairs, two content editors and one formatting
reviewer. Every discovery has concrete completed search-tool evidence. Discovery
reaches ten concurrent calls; the literature/plotting branches overlap for
approximately 548.5 seconds and both join before section writing.

### Exact sources throughout writing, compilation and review

The initial section writer and both content editors each receive the same
selected-source manifest, exact R/TikZ source text and exact export-wrapper
context. I checked all three invocation snapshots and prompt hashes against
the actual selected artifacts.

For all three manuscript outputs, the retained upstream raw response equals the
actual native completed agent message. Recomputing the original parse and then
the deterministic provenance transformation exactly reproduces the saved
effective result; the JSON worklogs are unchanged. The parsed controller
handoff is the effective result, not a later replacement of the final paper.

The baseline, v1 and v2 compilation snapshots are byte-identical to those
effective worker handoffs and to the sources recorded at compiler consumption.
Their copied source manifests and artifacts are exact. All three compiled PDFs
contain the selected JPEG bytes and visible exact source paths/checksums; the
peer-review prompts contain the text extracted from the corresponding actual
compiled PDF. There is no alternative figure recipe in the normalized
manuscripts and no late final-source mutation after scoring.

The fresh run regenerated its figures; their authoritative source hashes differ
from the separately corrected historical manuscript:

| Fresh figure | Exact stable source | SHA-256 |
| --- | --- | --- |
| Intercept error | `figure_code/fig_intercept_error/source.R` | `d2164cacbb40ae272e285dd0123744ced626b06c00bd67f9d17f1f866a3da3f4` |
| Residual workflow | `figure_code/fig_residual_workflow/source.tex` | `6f198c754d86c280d502725d53a5839058bbbc68480fa50ee82d1dd30cc77e65` |

Both sources match actual independent visualizer responses. Every published
source, wrapper, native PDF, preview and metadata alias equals its selected
renderer original. The R source is the fourth successful R render. The fourth
TikZ attempt fails with `columnwidth already defined`; the upstream controller
retains the third valid preview. Its published source correctly points to
`figure_sources/759f443e84894e47a2895fafea4b63d7/source.tex`, **not** the later
failed source. This selection is established by the retained preview hash and
successful render context, not directory recency. Both figures use the original
three-critic-round cap; no extra repair or manual image substitution follows it.

### Aggregation, reversion and stopping

Three complete ensembles each execute three sequential independent reviewers
and then a separate chair. I independently recomputed all **27 bounded integer
means**, including rounding: every saved field matches.

| Candidate | Overall before → after | Subaxis gain / drop | Observed decision |
| --- | --- | --- | --- |
| v1 | 3 → 3 | 2 / 0 | Accept neutral improvement; continue. |
| v2 | 3 → 3 | 0 / 1 | Reject degradation, retain v1 and stop. |

The final TeX and six-page delivered PDF are byte-identical to accepted v1.
No v3 candidate exists. Exactly one formatting review reports no issues for
both figures and both tables; there is no formatting editor or formatting
candidate. Thus the installed run demonstrates actual scored rejection,
reversion and early stopping, not merely a worklog label or a test fixture.

### Saved-source replay and limits

`validation/provenance-e2e-final-replay` completes with zero LLM calls and
re-renders all seven successful retained versions. I compared the actual
source/wrapper inputs and JPEG bytes for every original/replay pair: all are
identical. For both originals and replays, independent 300-DPI rasterization
of each native PDF produces the saved JPEG bytes. The failed eighth render is
retained as failed evidence and is not passed off as a successful replay.

The final PDF's exact source paths, source checksums and R-wrapper checksum are
visible and copyable, with underscores intact. I also inspected the final
provenance page visually; references are readable without clipping. The PDF
embeds both exact selected JPEGs.

Genuine limits remain: Semantic Scholar returns 119 HTTP 429 responses and five
HTTP 200 responses, yet no paper passes enrichment, so the verified citation
map is empty. PaperBanana examples are absent and use the authors' empty-example
fallback. These facts do not establish comprehensive literature coverage or
publication-quality science. The toy calculation and Overall 3 scores remain
workflow evidence. The historical derivative still has **zero new peer reviews**;
its correction must not be confused with this fresh three-ensemble run.
