---
name: "cost-overrun-prediction"
description: "Predict which projects will exceed budget using ML. Train on historical project data, classify risk level, and generate early warning reports."
homepage: "https://trailwise.com"
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

## Overview

Train a machine learning model on historical project data to predict which active projects are at risk of exceeding budget. Uses features like project size, phase, early-stage burn rate, vendor mix, and project type to classify overrun risk.

## When to Use

- You have 20+ completed projects with budget/actual data
- You want early warning (at 20-30% complete) on which projects will overrun
- You're tired of discovering overruns at 90% complete when it's too late

## Capabilities

- Binary classification: Will overrun / Will not overrun (threshold configurable)
- Risk scoring: 0-100 probability of overrun
- Feature importance: Which factors drive the prediction
- Early-stage prediction: Works at 20%+ project completion
- Multi-project batch scoring
- Model retraining pipeline with new project data

## Quick Start

```python
from dataclasses import dataclass
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
import joblib

@dataclass
class ProjectFeatures:
    project_id: str
    project_type: str          # "commercial", "residential", "industrial", "tenant_improvement"
    contract_value: float
    duration_planned_days: int
    percent_complete: float    # Current % complete at time of prediction
    spent_to_date: float
    committed_cost: float      # Signed contracts + POs not yet invoiced
    num_subcontractors: int
    num_change_orders: int
    change_order_value: float
    weather_delay_days: int
    num_rfis: int
    num_clashes_detected: int
    client_payment_delay_avg: float  # Average days late on client payments
    project_manager: str       # Could be encoded as feature
    region: str

    def to_dict(self) -> Dict:
        d = self.__dict__.copy()
        # Derived features
        d["burn_rate"] = self.spent_to_date / (self.percent_complete / 100) if self.percent_complete > 0 else 0
        d["overrun_pct_current"] = (self.committed_cost / self.contract_value - 1) * 100
        d["co_ratio"] = self.change_order_value / self.contract_value if self.contract_value else 0
        d["subcontractor_density"] = self.num_subcontractors / (self.contract_value / 100000) if self.contract_value else 0
        return d


class OverrunPredictor:
    """ML model to predict project cost overruns."""

    def __init__(self, overrun_threshold_pct: float = 5.0):
        """
        Args:
            overrun_threshold_pct: % over budget that counts as "overrun" (default 5%)
        """
        self.threshold = overrun_threshold_pct
        self.model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.feature_names = None
        self.is_trained = False

    def prepare_features(self, projects: List[ProjectFeatures]) -> Tuple[np.ndarray, np.ndarray]:
        """Convert project data to feature matrix and target vector."""
        df = pd.DataFrame([p.to_dict() for p in projects])

        # Encode categoricals
        for col in ["project_type", "region"]:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
                df = pd.concat([df.drop(col, axis=1), dummies], axis=1)

        # Drop non-numeric
        df = df.drop(columns=["project_id", "project_manager"], errors="ignore")

        # Target: did the project overrun by more than threshold?
        # In training data, final_cost must be available
        if "final_cost" in df.columns:
            y = (df["final_cost"] > df["contract_value"] * (1 + self.threshold / 100)).astype(int)
            df = df.drop(columns=["final_cost"])
        else:
            y = None

        self.feature_names = df.columns.tolist()
        X = df.values

        return X, y

    def train(self, projects: List[ProjectFeatures], final_costs: List[float]):
        """Train the model on historical completed projects."""
        # Add final costs to projects for target generation
        df_data = []
        for p, fc in zip(projects, final_costs):
            d = p.to_dict()
            d["final_cost"] = fc
            df_data.append(d)

        df = pd.DataFrame(df_data)

        # Encode categoricals
        for col in ["project_type", "region"]:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
                df = pd.concat([df.drop(col, axis=1), dummies], axis=1)

        df = df.drop(columns=["project_id", "project_manager"], errors="ignore")

        y = (df["final_cost"] > df["contract_value"] * (1 + self.threshold / 100)).astype(int)
        X_df = df.drop(columns=["final_cost"])
        self.feature_names = X_df.columns.tolist()
        X = X_df.values

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_proba = self.model.predict_proba(X_test_scaled)[:, 1]

        self.is_trained = True

        return {
            "accuracy": float((y_pred == y_test).mean()),
            "auc_roc": float(roc_auc_score(y_test, y_proba)) if len(np.unique(y_test)) > 1 else None,
            "samples_trained": len(X_train),
            "features_used": len(self.feature_names),
            "overrun_rate": float(y.mean())
        }

    def predict(self, project: ProjectFeatures) -> Dict:
        """Predict overrun risk for a single active project."""
        if not self.is_trained:
            return {"error": "Model not trained"}

        d = project.to_dict()

        # One-hot encode to match training features
        row = {}
        for fn in self.feature_names:
            row[fn] = d.get(fn, 0)

        X = np.array([[row[fn] for fn in self.feature_names]])
        X_scaled = self.scaler.transform(X)

        proba = self.model.predict_proba(X_scaled)[0]
        prediction = self.model.predict(X_scaled)[0]

        # Feature importance for this prediction
        importances = self.model.feature_importances_
        top_factors = sorted(
            zip(self.feature_names, importances),
            key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "project_id": project.project_id,
            "overrun_predicted": bool(prediction),
            "risk_score": round(float(proba[1]) * 100, 1),  # 0-100
            "risk_level": self._risk_level(proba[1]),
            "top_risk_factors": [
                {"factor": f, "importance": round(float(i), 3)}
                for f, i in top_factors
            ],
            "current_burn_rate": round(d["burn_rate"], 2),
            "current_overrun_pct": round(d["overrun_pct_current"], 1)
        }

    def _risk_level(self, probability: float) -> str:
        if probability > 0.7:
            return "HIGH — Overrun likely, take corrective action now"
        elif probability > 0.4:
            return "MEDIUM — Monitor closely, review burn rate"
        else:
            return "LOW — On track, no action needed"

    def save_model(self, path: str):
        """Save trained model for future use."""
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "threshold": self.threshold
        }, path)

    def load_model(self, path: str):
        """Load a previously trained model."""
        data = joblib.load(path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.feature_names = data["feature_names"]
        self.threshold = data["threshold"]
        self.is_trained = True
```

## Training Data Requirements

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

## Feature Importance (example from trained model)

| Factor | Importance | Interpretation |
|--------|------------|----------------|
| burn_rate | 0.28 | Spending faster than progress = strongest signal |
| co_ratio | 0.22 | Change orders as % of contract |
| overrun_pct_current | 0.18 | Already over budget at time of check |
| num_subcontractors | 0.12 | Coordination complexity |
| client_payment_delay_avg | 0.09 | Cash flow stress indicator |

## Edge Cases

1. **Early-stage projects (< 10% complete)** — Low signal, high noise. Flag as "insufficient data."
2. **Perfect record (no overruns in history)** — Model can't learn. Use synthetic data or industry benchmarks.
3. **Outlier projects** — One mega-project skewing the model. Use robust scaling.
4. **New project type** — No historical data for this type. Fall back to heuristic rules.
