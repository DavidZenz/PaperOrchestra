# Actual finite-data calculation. No figures are supplied: Codex must generate them.
args <- commandArgs(trailingOnly=TRUE)
destination <- if (length(args)) args[[1]] else "examples/code-figures/materials"
dir.create(destination, recursive=TRUE, showWarnings=FALSE)
x <- c(-2,-1,0,1,2)
y <- 2*x + 3
baseline <- 2*x
correction <- mean(y-baseline)
offsets <- c(0,1.5,3)
mae <- vapply(offsets, function(b) mean(abs(2*x+b-y)), numeric(1))
mse <- vapply(offsets, function(b) mean((2*x+b-y)^2), numeric(1))
observations <- data.frame(x=x,y=y,baseline=baseline,corrected=baseline+correction)
metrics <- data.frame(b=offsets,MAE=mae,MSE=mse)
write.csv(observations, file.path(destination,"observations.csv"), row.names=FALSE)
write.csv(metrics, file.path(destination,"metrics.csv"), row.names=FALSE)
markdown <- c(
  "# Actual R calculation on five synthetic observations", "",
  "One deterministic calculation; no stochastic repetitions, optimizer, external dataset, benchmark, timing or held-out evaluation.",
  "The same observations determine and evaluate the correction. No other experiments were run.", "",
  "| x | y | baseline 2x | corrected 2x+3 |", "|---:|---:|---:|---:|")
for (i in seq_along(x)) markdown <- c(markdown, sprintf("| %g | %g | %g | %g |",x[i],y[i],baseline[i],baseline[i]+correction))
markdown <- c(markdown,"", "Correction b = mean(y - 2x) = 3.","", "| Added b | Mean absolute error | Mean squared error |", "|---:|---:|---:|")
for (i in seq_along(offsets)) markdown <- c(markdown,sprintf("| %g | %g | %g |",offsets[i],mae[i],mse[i]))
markdown <- c(markdown,"", "Required generated statistical figure: fig_intercept_error. Plot the three recorded MSE values against b. No unmeasured points, uncertainty intervals or invented data.",
              "Code must be R/ggplot2. Keep this calculation reproducible and keep the numerical scope finite.")
writeLines(markdown,file.path(destination,"experimental_log.md"))
writeLines(capture.output(sessionInfo()),file.path(destination,"experiment-sessionInfo.txt"))
print(metrics)
