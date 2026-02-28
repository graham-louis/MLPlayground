"""Evaluation nodes — metrics, cross-validation, and explainability.

These nodes consume a trained model and test data to produce evaluation
artifacts.  Keeping evaluation separate from training means you can swap
models and re-evaluate without re-writing training logic.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)

ARTIFACTS_BASE: str = os.environ.get("ARTIFACTS_BASE", "/app/artifacts")


class MetricsNode(BaseNode):
    node_id = "metrics"
    display_name = "Metrics"
    description = (
        "Compute regression or classification metrics from predictions and ground truth."
    )
    category = "Evaluation"

    inputs = [
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="model", type=IOTypes.MODEL),
    ]
    outputs = [IOSlot(name="metrics", type=IOTypes.ARTIFACT)]

    class Params(BaseModel):
        target_column: str = "crop_yield"
        feature_columns: list[str] = []
        task: Literal["regression", "classification"] = "regression"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd

        df: pd.DataFrame = inputs["dataframe"]
        model = inputs["model"]

        feature_cols = params.feature_columns or [
            c for c in df.select_dtypes(include="number").columns
            if c != params.target_column
        ]
        df_clean = df[feature_cols + [params.target_column]].dropna()
        X = df_clean[feature_cols].values
        y_true = df_clean[params.target_column].values
        y_pred = model.predict(X)

        if params.task == "regression":
            from sklearn.metrics import (
                mean_absolute_error,
                mean_squared_error,
                r2_score,
            )
            metrics = {
                "r2": round(float(r2_score(y_true, y_pred)), 4),
                "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
                "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
                "n_samples": len(df_clean),
            }
        else:
            from sklearn.metrics import accuracy_score, f1_score
            metrics = {
                "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
                "f1_macro": round(float(f1_score(y_true, y_pred, average="macro")), 4),
                "n_samples": len(df_clean),
            }

        return {"metrics": metrics}


class CrossValNode(BaseNode):
    node_id = "cross_val"
    display_name = "Cross-Validation"
    description = "Evaluate a model using k-fold cross-validation and return mean ± std metrics."
    category = "Evaluation"

    inputs = [
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="model", type=IOTypes.MODEL),
    ]
    outputs = [IOSlot(name="metrics", type=IOTypes.ARTIFACT)]

    class Params(BaseModel):
        target_column: str = "crop_yield"
        feature_columns: list[str] = []
        cv_folds: int = 5
        scoring: str = "r2"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        from sklearn.model_selection import cross_val_score

        df = inputs["dataframe"]
        model = inputs["model"]

        feature_cols = params.feature_columns or [
            c for c in df.select_dtypes(include="number").columns
            if c != params.target_column
        ]
        df_clean = df[feature_cols + [params.target_column]].dropna()
        X = df_clean[feature_cols].values
        y = df_clean[params.target_column].values

        scores = cross_val_score(model, X, y, cv=params.cv_folds, scoring=params.scoring)
        metrics = {
            "scoring": params.scoring,
            "cv_folds": params.cv_folds,
            "mean": round(float(scores.mean()), 4),
            "std": round(float(scores.std()), 4),
            "scores": [round(float(s), 4) for s in scores],
        }
        return {"metrics": metrics}


class SHAPNode(BaseNode):
    node_id = "shap_explainer"
    display_name = "SHAP Explainer"
    description = (
        "Generate SHAP feature importance values and save a summary plot "
        "to artifacts/shap/. Returns the artifact path."
    )
    category = "Evaluation"

    inputs = [
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="model", type=IOTypes.MODEL),
    ]
    outputs = [
        IOSlot(name="shap_values", type=IOTypes.ARTIFACT),
        IOSlot(name="artifact_path", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        target_column: str = "crop_yield"
        feature_columns: list[str] = []
        max_display: int = 20
        sample_size: int = 200  # cap rows for speed

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        try:
            import shap
        except ImportError as exc:
            raise RuntimeError(
                "SHAPNode requires the shap package. Install with: pip install shap"
            ) from exc

        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend for servers
        import matplotlib.pyplot as plt

        df = inputs["dataframe"]
        model = inputs["model"]

        feature_cols = params.feature_columns or [
            c for c in df.select_dtypes(include="number").columns
            if c != params.target_column
        ]
        df_clean = df[feature_cols].dropna()
        X = df_clean.sample(
            min(params.sample_size, len(df_clean)), random_state=42
        )

        # Choose the right SHAP explainer for the model type
        if hasattr(model, "feature_importances_"):
            explainer = shap.TreeExplainer(model)
        else:
            explainer = shap.LinearExplainer(model, X)

        shap_values = explainer.shap_values(X)

        # Save summary plot
        shap_dir = os.path.join(ARTIFACTS_BASE, "shap")
        os.makedirs(shap_dir, exist_ok=True)
        plot_path = os.path.join(shap_dir, f"{uuid.uuid4()}_shap_summary.png")
        shap.summary_plot(
            shap_values,
            X,
            feature_names=feature_cols,
            max_display=params.max_display,
            show=False,
        )
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close()

        # Mean absolute SHAP per feature
        mean_shap = dict(
            zip(
                feature_cols,
                [round(float(v), 6) for v in np.abs(shap_values).mean(axis=0)],
            )
        )
        return {"shap_values": mean_shap, "artifact_path": plot_path}


class PlotROCNode(BaseNode):
    node_id = "plot_roc"
    display_name = "ROC Curve"
    description = "Plot a ROC curve for a binary classification model and save it to artifacts/."
    category = "Evaluation"

    inputs = [
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="model", type=IOTypes.MODEL),
    ]
    outputs = [IOSlot(name="artifact_path", type=IOTypes.ARTIFACT)]

    class Params(BaseModel):
        target_column: str
        feature_columns: list[str] = []

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.metrics import RocCurveDisplay

        df = inputs["dataframe"]
        model = inputs["model"]

        feature_cols = params.feature_columns or [
            c for c in df.select_dtypes(include="number").columns
            if c != params.target_column
        ]
        df_clean = df[feature_cols + [params.target_column]].dropna()
        X = df_clean[feature_cols].values
        y = df_clean[params.target_column].values

        plots_dir = os.path.join(ARTIFACTS_BASE, "plots")
        os.makedirs(plots_dir, exist_ok=True)
        path = os.path.join(plots_dir, f"{uuid.uuid4()}_roc.png")

        fig, ax = plt.subplots()
        RocCurveDisplay.from_estimator(model, X, y, ax=ax)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return {"artifact_path": path}
