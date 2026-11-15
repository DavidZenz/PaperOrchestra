# Actual finite arithmetic results

```json
{
  "x": [
    -2,
    -1,
    0,
    1,
    2
  ],
  "y": [
    -1,
    1,
    3,
    5,
    7
  ],
  "results": [
    {
      "b": 0,
      "predictions": [
        -4,
        -2,
        0,
        2,
        4
      ],
      "mean_absolute_error": 3.0,
      "mean_squared_error": 9.0
    },
    {
      "b": 1.5,
      "predictions": [
        -2.5,
        -0.5,
        1.5,
        3.5,
        5.5
      ],
      "mean_absolute_error": 1.5,
      "mean_squared_error": 2.25
    },
    {
      "b": 3,
      "predictions": [
        -1,
        1,
        3,
        5,
        7
      ],
      "mean_absolute_error": 0.0,
      "mean_squared_error": 0.0
    }
  ],
  "repetitions": 1,
  "evaluation": "same five synthetic points used to compute and evaluate correction; no held-out evaluation"
}
```

No other experiments were performed. b is the mean of residuals y-2x, equal to 3.
