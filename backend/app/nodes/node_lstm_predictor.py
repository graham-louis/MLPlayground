"""LSTM Predictor node — run inference with a saved LSTM checkpoint.

Loads a ``.pt`` state_dict saved by ``LSTMTrainerNode`` alongside its
``_arch.json`` sidecar, reconstructs the ``nn.Module``, and runs
forward-pass inference on a chosen split (train / test / holdout).

The sequences artifact produced by ``SequenceBuilderNode`` is read to
obtain pre-scaled arrays *and* the fitted ``scaler_y`` for inverse
transformation back to physical units.

Output DataFrame columns
------------------------
``actual``
    Ground-truth target values (inverse-scaled, original units).
``predicted``
    Model-predicted target values (inverse-scaled, original units).
``residual``
    ``actual - predicted``
``pct_error``
    ``residual / actual * 100``  (NaN where ``|actual| < 0.01``).
``sample_index``
    Sequential integer index that can be used as an x-axis for line plots.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)


class LSTMPredictorNode(BaseNode):
    node_id = "lstm_predictor"
    display_name = "LSTM Predictor"
    description = (
        "Load a trained LSTM checkpoint and run inference on a chosen data split "
        "(train / test / holdout).  Returns a DataFrame with actual, predicted, "
        "residual, and pct_error columns ready for downstream plot nodes."
    )
    category = "Modeling"

    inputs = [
        IOSlot(name="model",     type=IOTypes.MODEL),
        IOSlot(name="sequences", type=IOTypes.ARTIFACT),
    ]
    outputs = [
        IOSlot(name="predictions",  type=IOTypes.DATAFRAME),
        IOSlot(name="artifact_path",type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        split: Literal["train", "test", "holdout"] = Field(
            default="test",
            description="Which data split to run inference on.",
        )

    params = Params

    # ------------------------------------------------------------------
    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import joblib
        import torch

        # ── Locate model & arch files ───────────────────────────────────
        model_path: str  = inputs["model"]
        arch_path        = model_path.replace(".pt", "_arch.json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"LSTMPredictorNode: model file not found: '{model_path}'"
            )
        if not os.path.exists(arch_path):
            raise FileNotFoundError(
                f"LSTMPredictorNode: architecture sidecar not found: '{arch_path}'. "
                "Ensure the model was saved by LSTMTrainerNode."
            )

        with open(arch_path) as f:
            arch: dict = json.load(f)

        # ── Load sequences artifact ──────────────────────────────────────
        sequences_path: str = inputs["sequences"]
        if not os.path.exists(sequences_path):
            raise FileNotFoundError(
                f"LSTMPredictorNode: sequences artifact not found: '{sequences_path}'"
            )

        artifact = joblib.load(sequences_path)
        scaler_y = artifact["scaler_y"]

        split_map = {
            "train":   ("X_train",   "y_train"),
            "test":    ("X_test",    "y_test"),
            "holdout": ("X_holdout", "y_holdout"),
        }
        x_key, y_key = split_map[params.split]
        X: np.ndarray = artifact[x_key]
        y: np.ndarray = artifact[y_key]

        if X.shape[0] == 0:
            logger.warning(
                "LSTMPredictorNode: split '%s' is empty — returning empty DataFrame.",
                params.split,
            )
            empty_df = pd.DataFrame(columns=["sample_index", "actual", "predicted", "residual", "pct_error"])
            return {"predictions": empty_df, "artifact_path": model_path}

        # ── Reconstruct model ────────────────────────────────────────────
        # Import the builder so we don't duplicate architecture code.
        try:
            from app.nodes.node_lstm_trainer import _build_model
        except ImportError:
            # Inline fallback — reconstruct locally if import fails
            import torch.nn as nn

            def _build_model(n_features, lstm_units, dropout, bidirectional):  # type: ignore[misc]
                class _LSTM(nn.Module):
                    def __init__(self):
                        super().__init__()
                        self.lstm = nn.LSTM(n_features, lstm_units, batch_first=True, bidirectional=bidirectional)
                        d = 2 if bidirectional else 1
                        self.dropout = nn.Dropout(dropout)
                        self.fc1 = nn.Linear(lstm_units * d, 16)
                        self.relu = nn.ReLU()
                        self.fc2 = nn.Linear(16, 1)

                    def forward(self, x):
                        out, _ = self.lstm(x)
                        out = self.dropout(out[:, -1, :])
                        return self.fc2(self.relu(self.fc1(out)))

                return _LSTM()

        device = torch.device("cpu")
        model = _build_model(
            n_features=arch["n_features"],
            lstm_units=arch["lstm_units"],
            dropout=arch["dropout"],
            bidirectional=arch["bidirectional"],
        ).to(device)

        state_dict = torch.load(model_path, map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
        model.eval()

        # ── Forward pass ─────────────────────────────────────────────────
        X_t = torch.tensor(X, dtype=torch.float32, device=device)
        with torch.no_grad():
            y_pred_scaled = model(X_t).cpu().numpy()

        y_pred = scaler_y.inverse_transform(y_pred_scaled).ravel()
        y_true = scaler_y.inverse_transform(y).ravel()

        residual  = y_true - y_pred
        pct_error = np.where(
            np.abs(y_true) >= 0.01,
            residual / y_true * 100.0,
            np.nan,
        )

        predictions_df = pd.DataFrame({
            "sample_index": np.arange(len(y_true)),
            "actual":       np.round(y_true,  4),
            "predicted":    np.round(y_pred,  4),
            "residual":     np.round(residual, 4),
            "pct_error":    np.round(pct_error, 2),
        })

        logger.info(
            "LSTMPredictorNode: split='%s'  n=%d  mean_residual=%.4f",
            params.split, len(predictions_df), float(np.nanmean(residual)),
        )

        return {
            "predictions":  predictions_df,
            "artifact_path": model_path,
        }
