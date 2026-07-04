"""Cost overrun prediction — ML classification of project budget risk.

Train on historical completed projects, then predict which active projects
are at risk of exceeding budget.  Import this module; do not paste code
inline in SKILL.md.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
import joblib


@dataclass
class ProjectFeatures:
    project_id: str
    project_type: str            # "commercial", "residential", "industrial", "tenant_improvement"
    contract_value: float
    duration_planned_days: int
    percent_complete: float      # Current % complete at time of prediction
    spent_to_date: float
    committed_cost: float        # Signed contracts + POs not yet invoiced
    num_subcontractors: int
    num_change_orders: int
    change_order_value: float
    weather_delay_days: int
    num_rfis: int
    num_clashes_detected: int
    client_payment_delay_avg: float  # Average days late on client payments
    project_manager: str        # Could be encoded as feature
    region: str

    def to_dict(self) -> Dict:
        d = self.__dict__.copy()
        # Derived features
        d["burn_rate"] = (
            self.spent_to_date / (self.percent_complete / 100)
            if self.percent_complete > 0 else 0
        )
        d["overrun_pct_current"] = (self.committed_cost / self.contract_value - 1) * 100
        d["co_ratio"] = (
            self.change_order_value / self.contract_value
            if self.contract_value else 0
        )
        d["subcontractor_density"] = (
            self.num_subcontractors / (self.contract_value / 100000)
            if self.contract_value else 0
        )
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
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.feature_names: Optional[List[str]] = None
        self.is_trained = False

    # ------------------------------------------------------------------
    # Feature engineering (single source of truth — used by both branches)
    # ------------------------------------------------------------------
    def prepare_features(
        self,
        projects: List[ProjectFeatures],
        final_costs: Optional[List[float]] = None,
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Convert project data to feature matrix and target vector.

        When *final_costs* is provided (training branch), attaches
        ``final_cost`` to each project dict and extracts the overrun
        target (1 if final_cost exceeds contract_value by more than
        threshold %, else 0).  When omitted (predict branch), returns
        ``y = None``.
        """
        df_data = [p.to_dict() for p in projects]
        if final_costs is not None:
            for d, fc in zip(df_data, final_costs):
                d["final_cost"] = fc

        df = pd.DataFrame(df_data)

        # Encode categoricals
        for col in ["project_type", "region"]:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
                df = pd.concat([df.drop(col, axis=1), dummies], axis=1)

        # Drop non-numeric / identifier columns
        df = df.drop(columns=["project_id", "project_manager"], errors="ignore")

        # Target: did the project overrun by more than threshold?
        if "final_cost" in df.columns:
            y = (
                df["final_cost"]
                > df["contract_value"] * (1 + self.threshold / 100)
            ).astype(int)
            df = df.drop(columns=["final_cost"])
        else:
            y = None

        self.feature_names = df.columns.tolist()
        X = df.values
        return X, y

    # ------------------------------------------------------------------
    # Train branch
    # ------------------------------------------------------------------
    def train(self, projects: List[ProjectFeatures], final_costs: List[float]) -> Dict:
        """Train the model on historical completed projects."""
        X, y = self.prepare_features(projects, final_costs)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_proba = self.model.predict_proba(X_test_scaled)[:, 1]

        self.is_trained = True

        return {
            "accuracy": float((y_pred == y_test).mean()),
            "auc_roc": (
                float(roc_auc_score(y_test, y_proba))
                if len(np.unique(y_test)) > 1 else None
            ),
            "samples_trained": len(X_train),
            "features_used": len(self.feature_names),
            "overrun_rate": float(y.mean()),
        }

    # ------------------------------------------------------------------
    # Predict branch
    # ------------------------------------------------------------------
    def predict(self, project: ProjectFeatures) -> Dict:
        """Predict overrun risk for a single active project."""
        if not self.is_trained:
            return {"error": "Model not trained"}

        d = project.to_dict()

        # One-hot encode to match training features
        row = {fn: d.get(fn, 0) for fn in self.feature_names}
        X = np.array([[row[fn] for fn in self.feature_names]])
        X_scaled = self.scaler.transform(X)

        proba = self.model.predict_proba(X_scaled)[0]
        prediction = self.model.predict(X_scaled)[0]

        # Feature importance for this prediction
        importances = self.model.feature_importances_
        top_factors = sorted(
            zip(self.feature_names, importances),
            key=lambda x: x[1], reverse=True,
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
            "current_overrun_pct": round(d["overrun_pct_current"], 1),
        }

    def _risk_level(self, probability: float) -> str:
        if probability > 0.7:
            return "HIGH — Overrun likely, take corrective action now"
        elif probability > 0.4:
            return "MEDIUM — Monitor closely, review burn rate"
        else:
            return "LOW — On track, no action needed"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_model(self, path: str):
        """Save trained model for future use."""
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "threshold": self.threshold,
            },
            path,
        )

    def load_model(self, path: str):
        """Load a previously trained model."""
        data = joblib.load(path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.feature_names = data["feature_names"]
        self.threshold = data["threshold"]
        self.is_trained = True
