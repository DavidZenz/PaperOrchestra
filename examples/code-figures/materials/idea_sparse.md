# A finite intercept correction calculation with reproducible figures

This is a synthetic teaching-note workflow demonstration, not a new scientific
result. Five inputs x = [-2,-1,0,1,2] have targets y = 2x+3. A fixed predictor
returns 2x. Compute the mean residual on these same points, b = mean(y-2x)=3,
and add it to the predictions. The experimental log is the only measured data.
There is no optimizer, architecture, external dataset, stochastic experiment,
held-out evaluation or timing result. The calculation is implemented in base R.
Scope all claims to these exact five observations; literature supplies context,
not extra measurements or claims of novelty.

Generate exactly two essential figures, with all source code retained:

1. `fig_intercept_error`: a statistical plot, `plot_type` `plot`, from
   `experimental_log.md`. Show the three measured MSE values at b=0,1.5,3.
   Use R/ggplot2. This plot is evidence of the finite arithmetic only.
2. `fig_residual_workflow`: a scientific schematic, `plot_type` `diagram`, from
   `idea.md`. Show input x and target y; baseline 2x; residual y-2x; mean
   residual b=3; corrected prediction 2x+b; evaluation on the same five points.
   Indicate the data dependency from observed residuals to the scalar correction.
   Use LaTeX/TikZ, mathematical labels, and no unrelated modules or experiments.

No figures are supplied. Separate Codex workers must plan, style, generate code,
critique the rendered figures, and write captions through the normal workflow.
The flow diagram should make the computation understandable; it adds no evidence
of predictive generalization. Native editable `.R` and `.tex` sources and their
vector PDFs should be retained alongside the manuscript-compatible previews.
