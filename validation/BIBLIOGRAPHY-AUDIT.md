# Bibliography audit — 2026-11-16

The original project explicitly implements reference discovery, BibTeX generation,
citation-library handoffs and bibliography compilation. Those components are
present in this port. The real mixed-runtime demonstration nevertheless produced
**zero accepted references**, and its first content revision removed the empty
bibliography. This is a failed live reference-collection outcome and a gap in our
validation of a reference-bearing paper. A completed controller run does not
establish that its manuscript has a usable reference list.

## Upstream contract

These findings refer to upstream commit
`ca1b3fa01c2970fc7cda32d16245db38d57b3f56`, not a claim about a later revision.

- `methods/agents/literature_review_agent.py`: separate model searches discover
  candidates; Semantic Scholar enriches candidates. Accepted records produce
  `references.bib`, `citation_map.json`, section `citation_candidates`, and the
  introduction/related-work template. Title matching, cutoff and abstract filters
  apply. Enrichment exceptions are swallowed by upstream.
- `methods/prompts/literature_review_agent.py`: the synthesis worker may cite only
  collected papers, using exact supplied keys. The generated minimum is
  `int(number_of_papers * 0.9)`. For zero papers it becomes zero; there is no
  nonempty-reference precondition in the original controller.
- `methods/agents/section_writing_agent.py`: the section writer receives the
  enriched outline, filled template, reference titles/abstracts/keys and the
  instruction to cite that library. An empty map is rendered as
  `No citation data provided.`
- `methods/paper_writer_with_plotting.py` and `methods/paper_writer.py` copy
  `references.bib` into the writeup. The content editor receives the allowed
  citation map too; adding unapproved keys is prohibited.
- `utils/pdf_utils.py`: compilation runs pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX.
  The original success check requires a resulting PDF and no timeout, rather than
  zero exit codes from every command or a nonempty bibliography.

These are preserved upstream behaviors, including their permissive failure
handling. Requiring a nonempty library or treating a BibTeX error as a failed
paper would be a separately documented adaptation to the original rules.

## What happened in the actual output

The audit reads the frozen `validation/multiruntime-e2e-final/` artifacts and makes
**zero model calls**. The machine-readable
[receipt](bibliography-audit.json) records hashes and the manuscript stages.

1. The actual HTTP trace contains **141 Semantic Scholar responses: 138 HTTP 429
   and three HTTP 200**. No candidate entered the accepted paper registry.
   `literature_agent_output/citation_map.json` is `{}` and `references.bib` is
   zero bytes. The same empty bibliography reached the writeup and refinement
   workspaces.
2. The literature synthesis and initial section-writer outputs retained
   `\bibliographystyle{plain}` and `\bibliography{references}`, but contained no
   citation commands. The initial BibTeX log reports no `\citation` commands and
   zero used entries.
3. The first content-edit call, `91ea0e37b9c0444c9ae8cebcd2a3f46c`, native
   invocation `85fdaedb76e744e0b7e388a07bcdbfbf`, explicitly records:
   “Removed repeated scope statements, the empty bibliography, and duplicated
   provenance material.” It also records that it added no citations because the
   permitted citation map was empty.
4. Both its original parsed response and its effective provenance-normalized
   response lack bibliography commands. The figure-source adapter did not remove
   those commands. All later revisions and the final manuscript remain without
   citations or a reference list. Subsequent BibTeX logs report missing citation,
   bibliography-data and bibliography-style commands; the original PDF-based
   compilation criterion still allowed the controller to finish.

The three HTTP 200 receipts retain response hashes, not response bodies or
per-candidate rejection reasons. The historical evidence cannot distinguish
empty search results, title/cutoff/abstract rejection, or an enrichment exception
for those three responses. No specific rejection cause is asserted for them.
The retained earlier corrected manuscript at `output/pdf/manuscript/` and the
earlier provenance demonstration also have empty bibliography files and no
final citation commands; this limitation is not exclusive to the latest PDF.

## Additional controlled validation

Four regression tests now exercise the relevant path without external model or
search requests:

- Actual literature-controller output and synthesis inputs carry accepted
  records and exact citation keys into the actual section-writer prompt.
- Zero accepted records reproduce upstream's empty bibliography and zero minimum
  citation requirement, documenting the failure mode rather than accepting it
  as paper readiness.
- Figure-source normalization preserves citations, embedded `.bib` content and
  bibliography commands in section, content and formatting result formats.
- The actual vendored upstream compiler runs real pdfLaTeX/BibTeX on a labelled
  bibliography fixture after provenance normalization. Its PDF contains a
  References heading and the cited entry, and its `.bbl` contains the exact key.

The controlled tests use explicitly labelled fixture literature. They establish
the code path, not successful live retrieval or scientific reference quality.
The post-audit full suite passes **298 tests in 27.456 seconds**, with zero
external model calls and no skips. This extends the historical 294-test suite;
it does not change the frozen installed bundle tested by the earlier live run.
See [the test log](bibliography-tests.log). The first focused run caught a
test expectation that ignored `plain.bst` sentence casing; that expectation was
corrected. The bibliography rendered correctly in that run too.

## Scope and remaining work

No controller, prompt, installed skill, frozen run, manuscript or archive was
changed by this audit. No new intentional deviation or scientific/output
adaptation was introduced; only tests and validation documentation were added.
The earlier completion evidence remains controller/provenance evidence. It must
not be interpreted as successful live bibliography validation.

A future reference-bearing real run must demonstrate nonempty verified records,
valid in-text keys, successful BibTeX resolution and a visible reference list.
Any added bibliography readiness gate, rate-limit retry policy or alternative
metadata provider must be documented separately from upstream control flow.
