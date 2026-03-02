"""Modeling nodes — train and persist ML models.

TrainerNode accepts a prepared DataFrame (features + target) and trains a
sklearn-compatible model.  It outputs the fitted model object, evaluation
metrics as a dict, and the path to the serialized artifact on disk.

Design decision: the node *receives* its DataFrame from upstream nodes (via
the graph wiring) rather than loading its own data.  This separates data
preparation (handled by source/transform nodes) from training logic, making
each independently swappable.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Literal, Optional

import joblib
import numpy as np
from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)

ARTIFACTS_DIR: str = os.environ.get("ARTIFACTS_BASE", "/app/artifacts") + "/models"


class TrainerNode(BaseNode):
    node_id = "trainer"
    display_name = "Trainer"
    description = (
        "Train a regression model on a prepared DataFrame. "
        "Outputs the fitted model, evaluation metrics, and the artifact path."
    )
    category = "Modeling"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="model", type=IOTypes.MODEL),
        IOSlot(name="metrics", type=IOTypes.ARTIFACT),
        IOSlot(name="artifact_path", type=IOTypes.ARTIFACT),
        IOSlot(name="feature_names", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        model_type: Literal[
            "linear_regression", "random_forest", "gradient_boosting"
        ] = "random_forest"
        target_column: str = "crop_yield"
        feature_columns: list[str] = []  # empty = all columns except target
        test_size: float = 0.2
        random_state: int = 42

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import mean_squared_error, r2_score
        from sklearn.model_selection import train_test_split

        df: pd.DataFrame = inputs["dataframe"]

        if params.target_column not in df.columns:
            raise ValueError(
                f"TrainerNode: target column '{params.target_column}' not in DataFrame. "
                f"Available: {list(df.columns)}"
            )

        feature_cols = params.feature_columns or [
            c for c in df.select_dtypes(include="number").columns
            if c != params.target_column
        ]
        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"TrainerNode: feature columns not found: {missing}")

        df_clean = df[feature_cols + [params.target_column]].dropna()
        if len(df_clean) < 10:
            raise ValueError(
                f"TrainerNode: only {len(df_clean)} rows after dropping nulls. Need ≥10."
            )

        X = df_clean[feature_cols].values
        y = df_clean[params.target_column].values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=params.test_size, random_state=params.random_state
        )

        model_map = {
            "linear_regression": LinearRegression(),
            "random_forest": RandomForestRegressor(
                n_estimators=100, random_state=params.random_state
            ),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=100, random_state=params.random_state
            ),
        }
        model = model_map[params.model_type]
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        # Feature importances
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_.tolist()
        elif hasattr(model, "coef_"):
            coef = np.abs(model.coef_)
            importances = (coef / (coef.sum() + 1e-8)).tolist()
        else:
            importances = [1.0 / len(feature_cols)] * len(feature_cols)

        metrics = {
            "r2": round(r2, 4),
            "rmse": round(rmse, 4),
            "n_samples": len(df_clean),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "feature_importances": dict(zip(feature_cols, importances)),
        }

        # Persist model artifact
        run_id = str(uuid.uuid4())
        artifact_path: Optional[str] = None
        try:
            os.makedirs(ARTIFACTS_DIR, exist_ok=True)
            artifact_path = os.path.join(ARTIFACTS_DIR, f"{run_id}.pkl")
            joblib.dump({"model": model, "features": feature_cols}, artifact_path)
        except Exception as exc:
            logger.warning("TrainerNode: failed to persist artifact: %s", exc)

        return {
            "model": model,
            "metrics": metrics,
            "artifact_path": artifact_path or "",
            "feature_names": feature_cols,
        }


class HyperparamSearchNode(BaseNode):
    node_id = "hyperparam_search"
    display_name = "Hyperparameter Search"
    description = (
        "Run AutoML via PyCaret to compare all regression algorithms "
        "and return the best-performing model."
    )
    category = "Modeling"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="model", type=IOTypes.MODEL),
        IOSlot(name="metrics", type=IOTypes.ARTIFACT),
        IOSlot(name="artifact_path", type=IOTypes.ARTIFACT),
        IOSlot(name="feature_names", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        target_column: str = "crop_yield"
        feature_columns: list[str] = []
        test_size: float = 0.2

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd
        from sklearn.metrics import mean_squared_error, r2_score

        try:
            from pycaret.regression import compare_models, pull, setup
        except ImportError as exc:
            raise RuntimeError(
                "HyperparamSearchNode requires pycaret. "
                "Install with: pip install 'pycaret[full]'"
            ) from exc

        df: pd.DataFrame = inputs["dataframe"]
        feature_cols = params.feature_columns or [
            c for c in df.select_dtypes(include="number").columns
            if c != params.target_column
        ]
        df_clean = df[feature_cols + [params.target_column]].dropna().copy()

        setup(
            data=df_clean,
            target=params.target_column,
            session_id=42,
            train_size=1.0 - params.test_size,
            verbose=False,
            html=False,
            log_experiment=False,
            system_log=False,
        )
        best_model = compare_models(sort="RMSE", verbose=False, errors="ignore")

        X_test = df_clean[feature_cols].iloc[int(len(df_clean) * (1 - params.test_size)):]
        y_test = df_clean[params.target_column].iloc[int(len(df_clean) * (1 - params.test_size)):]
        y_pred = best_model.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        comparison_df = pull()
        best_label = comparison_df.index[0] if len(comparison_df) > 0 else "best"

        metrics = {
            "r2": round(r2, 4),
            "rmse": round(rmse, 4),
            "best_model_label": str(best_label),
        }

        run_id = str(uuid.uuid4())
        artifact_path: Optional[str] = None
        try:
            os.makedirs(ARTIFACTS_DIR, exist_ok=True)
            artifact_path = os.path.join(ARTIFACTS_DIR, f"{run_id}_pycaret.pkl")
            joblib.dump({"model": best_model, "features": feature_cols}, artifact_path)
        except Exception as exc:
            logger.warning("HyperparamSearchNode: failed to persist artifact: %s", exc)

        return {
            "model": best_model,
            "metrics": metrics,
            "artifact_path": artifact_path or "",
            "feature_names": feature_cols,
        }


class SaveModelNode(BaseNode):
    node_id = "save_model"
    display_name = "Save Model"
    description = "Persist a fitted model to a named artifact path."
    category = "Modeling"

    inputs = [
        IOSlot(name="model", type=IOTypes.MODEL),
        IOSlot(name="feature_names", type=IOTypes.ARTIFACT),
    ]
    outputs = [IOSlot(name="artifact_path", type=IOTypes.ARTIFACT)]

    class Params(BaseModel):
        name: str = "model"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        model = inputs["model"]
        feature_names = inputs.get("feature_names", [])
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        path = os.path.join(ARTIFACTS_DIR, f"{params.name}.pkl")
        joblib.dump({"model": model, "features": feature_names}, path)
        return {"artifact_path": path}


class PredictorNode(BaseNode):
    """Apply a trained model to a DataFrame and return predictions.

    Integrates tightly with ``TrainerNode``: wire the ``model`` and
    ``feature_names`` outputs from a trainer directly to the matching inputs
    here.  The node supports:

    * **Residual analysis** — when ``target_column`` is non-empty and the
      column exists in the input DataFrame, the output includes ``actual``,
      ``predicted``, ``residual``, and ``pct_error`` columns alongside any
      ``id_columns`` you request (e.g. ``year``, ``county``).
    * **Pure inference** — when ``target_column`` is blank or absent the output
      only contains ``predicted`` (renamed via ``output_column_name``) plus
      any requested ``id_columns``.
    """

    node_id = "predictor"
    display_name = "Predictor"
    description = (
        "Apply a trained model to a DataFrame.  Wire the model and "
        "feature_names outputs from a Trainer node.  When a target column is "
        "provided the output also includes residuals for diagnostic plots."
    )
    category = "Modeling"

    inputs = [
        IOSlot(name="model", type=IOTypes.MODEL),
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="feature_names", type=IOTypes.ARTIFACT),
    ]
    outputs = [
        IOSlot(name="predictions", type=IOTypes.DATAFRAME),
    ]

    class Params(BaseModel):
        target_column: str = ""
        """If set and column exists in the DataFrame, residuals are computed."""
        feature_columns: list[str] = []
        """Override inferred feature list.  Useful when feature_names is not wired."""
        id_columns: list[str] = []
        """Pass-through columns included in the output (e.g. year, county)."""
        output_column_name: str = "predicted_yield"
        """Name of the predicted-value column in the output DataFrame."""

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd

        model = inputs["model"]
        df: pd.DataFrame = inputs["dataframe"]

        # ── Resolve feature columns ──────────────────────────────────────────
        # Priority: explicit params > wired feature_names > all numeric columns
        feature_cols: list[str] = (
            params.feature_columns
            or inputs.get("feature_names") or []
        )
        if not feature_cols:
            exclude = set()
            if params.target_column:
                exclude.add(params.target_column)
            if params.id_columns:
                exclude.update(params.id_columns)
            feature_cols = [
                c for c in df.select_dtypes(include="number").columns
                if c not in exclude
            ]

        # Validate
        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"PredictorNode: feature columns not found in DataFrame: {missing}. "
                f"Available: {list(df.columns)}"
            )

        # Drop rows where features are null
        df_clean = df.dropna(subset=feature_cols).reset_index(drop=True)
        X = df_clean[feature_cols].values
        y_pred = model.predict(X)

        # ── Assemble output ──────────────────────────────────────────────────
        out_cols: dict[str, Any] = {}

        # Include requested id/passthrough columns
        for col in params.id_columns:
            if col in df_clean.columns:
                out_cols[col] = df_clean[col].values

        out_cols[params.output_column_name] = y_pred

        has_target = (
            params.target_column
            and params.target_column in df_clean.columns
        )
        if has_target:
            y_true = df_clean[params.target_column].values
            residuals = y_true - y_pred
            pct_err = np.where(
                y_true != 0, np.abs(residuals / y_true) * 100.0, np.nan
            )
            out_cols["actual"] = y_true
            out_cols["residual"] = residuals
            out_cols["pct_error"] = pct_err

        predictions_df = pd.DataFrame(out_cols)
        return {"predictions": predictions_df}
