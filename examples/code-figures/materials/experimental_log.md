# Actual R calculation on five synthetic observations

One deterministic calculation; no stochastic repetitions, optimizer, external dataset, benchmark, timing or held-out evaluation.
The same observations determine and evaluate the correction. No other experiments were run.

| x | y | baseline 2x | corrected 2x+3 |
|---:|---:|---:|---:|
| -2 | -1 | -4 | -1 |
| -1 | 1 | -2 | 1 |
| 0 | 3 | 0 | 3 |
| 1 | 5 | 2 | 5 |
| 2 | 7 | 4 | 7 |

Correction b = mean(y - 2x) = 3.

| Added b | Mean absolute error | Mean squared error |
|---:|---:|---:|
| 0 | 3 | 9 |
| 1.5 | 1.5 | 2.25 |
| 3 | 0 | 0 |

Required generated statistical figure: fig_intercept_error. Plot the three recorded MSE values against b. No unmeasured points, uncertainty intervals or invented data.
Code must be R/ggplot2. Keep this calculation reproducible and keep the numerical scope finite.
