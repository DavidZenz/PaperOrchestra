# A finite intercept correction calculation

This is a tiny workflow demonstration using synthetic data, not a new research
result or a claim of novelty. There are five input values x = [-2,-1,0,1,2] and
targets y = 2x + 3. A fixed baseline predicts 2x. A corrected predictor adds a
constant b equal to the mean residual on these same five values. This gives b=3.
The purpose is to document the arithmetic and demonstrate that the correction
removes a constant error on these exact five points. No generalization, held-out
evaluation, statistical inference or computational speed comparison was measured.

Use the supplied results as the only numerical evidence. The experiment uses
plain Python arithmetic without an optimizer, a learned architecture, external
dataset or framework. Related literature can provide context about constant
residual correction but cannot supply extra experiments. The provided figure
shows the exact sensitivity of error to b and should be included once.
