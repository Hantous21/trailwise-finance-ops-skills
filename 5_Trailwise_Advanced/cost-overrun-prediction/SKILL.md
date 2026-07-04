---
name: "cost-overrun-prediction"
description: "Predict which active projects will exceed budget using ML classification. Use when you have 20+ completed projects with budget/actual data and want early warning on overrun risk."
homepage: "https://trailwise.com"
disable model invocation: true
metadata:
  trailwise:
    emoji: "🤖"
    category: "predictive-analytics"
    os: ["darwin", "linux", "win32"]
    requires:
      bins: ["python3"]
    optional_deps: ["scikit-learn", "pandas", "numpy", "joblib"]
---

# Cost Overrun Prediction

Train a gradient-boosting classifier on historical project data to predict which active projects will overrun. Uses contract value, burn rate, change-order volume, and payment behaviour to classify risk. All code lives in `scripts/cost_overrun_prediction.py` — import it, do not paste code inline.

## Workflow — Train

1. Gather ≥ 20 completed projects with known `final_cost` (see Training Data Requirements).
2. Build `ProjectFeatures` objects and call `OverrunPredictor(overrun_threshold_pct=5.0)`.
3. Call `predictor.train(projects, final_costs)` → returns accuracy, AUC-ROC, overrun rate.
4. Call `predictor.save_model("overrun_model.joblib")` to persist for the predict branch.

## Workflow — Predict

1. Load a saved model: `predictor.load_model("overrun_model.joblib")`.
2. Build a `ProjectFeatures` object for the active project (must be ≥ 20% complete).
3. Call `predictor.predict(project)` → returns `risk_score` (0-100), `risk_level`, top five risk factors, and current burn-rate/overrun snapshot.
4. Escalate HIGH-risk projects immediately; schedule MEDIUM for weekly review.

## Controls

- **20% complete threshold** — never predict below 20% completion; signal is too noisy and false positives dominate.
- **Burn rate is the strongest signal** — investigate any project whose burn rate exceeds its % complete.
- **Change-order ratio (co_ratio)** — a rising CO ratio early in the project is a leading indicator, not a lagging one.
- **Overrun threshold is configurable** — default 5%; lower to 3% for tight portfolios, raise to 10% for high-margin tolerance.
- **No perfect records** — if zero historical overruns exist, inject synthetic negatives or industry benchmarks before training.

## Reference — Feature Importance (example from trained model)

| Factor | Importance | Interpretation |
|--------|------------|----------------|
| burn_rate | 0.28 | Spending faster than progress = strongest signal |
| co_ratio | 0.22 | Change orders as % of contract |
| overrun_pct_current | 0.18 | Already over budget at time of check |
| num_subcontractors | 0.12 | Coordination complexity |
| client_payment_delay_avg | 0.09 | Cash flow stress indicator |

## Reference — Training Data Requirements

Minimum 20 completed projects with:

| Feature | Why it matters |
|---------|---------------|
| Contract value | Larger projects have different overrun patterns |
| Project type | Commercial vs residential have different risk profiles |
| % complete at prediction | Early predictions are noisier |
| Burn rate | Spending faster than progress = red flag |
| Change order count/value | COs are the #1 cause of overruns |
| Number of subcontractors | More subs = more coordination risk |
| RFI count | High RFI volume indicates design ambiguity |
| Client payment delay | Cash flow stress causes corner-cutting |

## Edge Cases

1. **Early-stage (< 10% complete)** — flag as "insufficient data"; do not score.
2. **Perfect record (no overruns)** — model cannot learn; use synthetic data or industry benchmarks.
3. **Outlier mega-project** — skews the model; use robust scaling or exclude.
4. **New project type** — no historical data; fall back to heuristic rules.

## Call to Action

Run `python3 scripts/cost_overrun_prediction.py` to smoke-test the predictor against sample fixture data.
