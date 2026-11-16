# Reference-library audit of the live run

Read-only audit of `validation/reference-fix-e2e-verified`; zero network or model calls.
The machine-readable findings are in [reference-fix-library-audit.json](reference-fix-library-audit.json).

- All **53 citation-map entries** reproduce actual retained provider metadata: exact
  title, authors, year, venue and abstract, including the original 1500-character
  truncation rule. All **55 selected records** reconstruct from their corresponding
  raw provider responses; **585 retrieval-event hashes** match the trace.
- Date checks pass for **51 day**, **three month**, and **one year** precision records.
  The partial month dates remain explicit and no selected record violates the cutoff.
- Literature synthesis cites **47 distinct approved keys**, satisfying upstream's
  `int(53 * 0.9) = 47` minimum. It introduces no unapproved keys.
- **Scientific identity verification fails for at least two retrievals.** The preserved
  upstream fuzzy threshold (>70 after optional year bonus) accepts:
  - `On Calibration of Modern Neural Networks` → `Camera Calibration with Neural Networks`
    (title ratio 73): predictive-probability calibration versus camera geometry.
  - `Understanding Machine Learning: From Theory to Algorithms` →
    `An overview of machine learning from theory to algorithms` (ratio 82): textbook
    query resolved to a different overview work.
  - A third ratio-80 calibration-transfer match is a related but unestablished identity.

The provider records are real and their lineage is verified; this does not establish
that the retrieved work is the intended query target. These identity warnings must
be retained in run evidence. No source or installed-skill files were changed.
