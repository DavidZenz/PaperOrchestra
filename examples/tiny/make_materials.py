"""Deterministic actual calculation and supplied figure for the real agent run."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

base = Path(__file__).resolve().parent / "materials"
figures = base / "figures"
figures.mkdir(parents=True, exist_ok=True)
x = [-2, -1, 0, 1, 2]
y = [2 * v + 3 for v in x]
offsets = [0, 1.5, 3]
metrics = []
for b in offsets:
    prediction = [2 * v + b for v in x]
    metrics.append({"b": b, "predictions": prediction,
                    "mean_absolute_error": sum(abs(p-t) for p,t in zip(prediction,y)) / len(x),
                    "mean_squared_error": sum((p-t)**2 for p,t in zip(prediction,y)) / len(x)})
log = {"x": x, "y": y, "results": metrics, "repetitions": 1,
       "evaluation": "same five synthetic points used to compute and evaluate correction; no held-out evaluation"}
(base / "experimental_log.md").write_text("# Actual finite arithmetic results\n\n```json\n" + json.dumps(log, indent=2) + "\n```\n\nNo other experiments were performed. b is the mean of residuals y-2x, equal to 3.\n")
fig, ax = plt.subplots(figsize=(4, 2.5))
ax.plot(offsets, [r["mean_squared_error"] for r in metrics], "o-")
ax.set(xlabel="Added intercept b", ylabel="Mean squared error", xticks=offsets)
fig.tight_layout()
fig.savefig(figures / "intercept_error.png", dpi=120)
plt.close(fig)
(figures / "info.json").write_text(json.dumps([{"name": "intercept_error.png", "caption": "Mean squared error on the five supplied synthetic points for intercepts 0, 1.5, and 3; the measured errors are 9, 2.25, and 0."}], indent=2))
print(json.dumps(log))
