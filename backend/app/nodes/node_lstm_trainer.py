"""LSTM Trainer node — train a Bidirectional LSTM in PyTorch.

Accepts a sequences artifact (produced by ``SequenceBuilderNode``) and
trains a configurable Bidirectional LSTM regression model for time-series
prediction.  Architecture and weights are saved as sidecar files so that
``LSTMPredictorNode`` can reconstruct the model without re-training.

Saved files (all under ``ARTIFACTS_BASE/models/``)
---------------------------------------------------
``<run_id>.pt``
    PyTorch ``state_dict`` (CPU tensors — safe to load anywhere).
``<run_id>_arch.json``
    Architecture hyper-parameters needed to reconstruct ``nn.Module``.
``<run_id>_metrics.json``
    Evaluation metrics: R², MAPE on test and holdout.
``<run_id>_history.json``
    Per-epoch ``{train_loss, val_loss}`` for learning-curve plots.

Architecture
------------
``Input(seq_length, n_features)``
  → ``Bidirectional LSTM(lstm_units)`` (or uni-directional when
    ``bidirectional=False``) → ``Dropout`` → ``Linear(16)`` → ``ReLU``
  → ``Linear(1)``

This mirrors the Keras / TensorFlow model in ``lstm_model_lab.py`` but
runs entirely in PyTorch, which is already present in the project's
dependencies.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)

ARTIFACTS_BASE: str = os.environ.get("ARTIFACTS_BASE", "/app/artifacts")
MODELS_DIR: str = os.path.join(ARTIFACTS_BASE, "models")


# ── PyTorch model definition ────────────────────────────────────────────────

def _build_model(n_features: int, lstm_units: int, dropout: float, bidirectional: bool):
    """Construct and return an untrained ``SoilMoistureLSTM`` nn.Module."""
    import torch.nn as nn

    class SoilMoistureLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=n_features,
                hidden_size=lstm_units,
                batch_first=True,
                bidirectional=bidirectional,
            )
            direction_mult = 2 if bidirectional else 1
            self.dropout = nn.Dropout(dropout)
            self.fc1 = nn.Linear(lstm_units * direction_mult, 16)
            self.relu = nn.ReLU()
            self.fc2 = nn.Linear(16, 1)

        def forward(self, x):
            # x: (batch, seq_len, n_features)
            lstm_out, _ = self.lstm(x)
            # Take the last time step
            out = lstm_out[:, -1, :]
            out = self.dropout(out)
            out = self.relu(self.fc1(out))
            return self.fc2(out)

    return SoilMoistureLSTM()


# ── Node ────────────────────────────────────────────────────────────────────

class LSTMTrainerNode(BaseNode):
    node_id = "lstm_trainer"
    display_name = "LSTM Trainer"
    description = (
        "Train a Bidirectional LSTM (PyTorch) on sequences produced by the "
        "Sequence Builder node.  Outputs the model checkpoint path, evaluation "
        "metrics, training-loss history, and the feature name list."
    )
    category = "Modeling"

    inputs = [
        IOSlot(name="sequences", type=IOTypes.ARTIFACT),
    ]
    outputs = [
        IOSlot(name="model",        type=IOTypes.MODEL),
        IOSlot(name="metrics",      type=IOTypes.ARTIFACT),
        IOSlot(name="artifact_path",type=IOTypes.ARTIFACT),
        IOSlot(name="history",      type=IOTypes.ARTIFACT),
        IOSlot(name="feature_names",type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        lstm_units: Literal[16, 32, 64, 128] = Field(
            default=64,
            description="Number of hidden units per LSTM layer.",
        )
        dropout: float = Field(
            default=0.2, ge=0.0, le=0.5,
            description="Dropout probability applied after the LSTM layer.",
        )
        learning_rate: float = Field(
            default=0.001, gt=0.0,
            description="Adam optimizer learning rate.",
        )
        epochs: int = Field(
            default=20, ge=1, le=500,
            description="Number of full passes over the training data.",
        )
        batch_size: int = Field(
            default=64, ge=1,
            description="Mini-batch size for SGD.",
        )
        bidirectional: bool = Field(
            default=True,
            description="Use a bidirectional LSTM (processes sequence forwards and backwards).",
        )
        model_name: str = Field(
            default="lstm_soil_moisture",
            description="Stem used when naming the saved checkpoint files.",
        )

    params = Params

    # ------------------------------------------------------------------
    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import joblib
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
        from sklearn.metrics import r2_score, mean_absolute_percentage_error

        # Force CPU (matches original script's CUDA_VISIBLE_DEVICES=-1)
        device = torch.device("cpu")

        # ── Load sequences artifact ──────────────────────────────────────
        sequences_path: str = inputs["sequences"]
        if not os.path.exists(sequences_path):
            raise FileNotFoundError(
                f"LSTMTrainerNode: sequences artifact not found at '{sequences_path}'"
            )

        artifact = joblib.load(sequences_path)
        X_train: np.ndarray = artifact["X_train"]
        y_train: np.ndarray = artifact["y_train"]
        X_test:  np.ndarray = artifact["X_test"]
        y_test:  np.ndarray = artifact["y_test"]
        X_holdout: np.ndarray = artifact["X_holdout"]
        y_holdout: np.ndarray = artifact["y_holdout"]
        scaler_y               = artifact["scaler_y"]
        feature_names: list[str] = artifact["feature_names"]
        n_features:  int       = artifact["n_features"]
        seq_length:  int       = artifact["seq_length"]

        if X_train.shape[0] == 0:
            raise ValueError("LSTMTrainerNode: training split is empty.")

        logger.info(
            "LSTMTrainerNode: X_train=%s  X_test=%s  X_holdout=%s  n_features=%d",
            X_train.shape, X_test.shape, X_holdout.shape, n_features,
        )

        # ── Build model ─────────────────────────────────────────────────
        model = _build_model(
            n_features=n_features,
            lstm_units=params.lstm_units,
            dropout=params.dropout,
            bidirectional=params.bidirectional,
        ).to(device)

        optimizer = torch.optim.Adam(model.parameters(), lr=params.learning_rate)
        criterion = nn.MSELoss()

        # ── DataLoaders ──────────────────────────────────────────────────
        def to_tensor(x: np.ndarray) -> torch.Tensor:
            return torch.tensor(x, dtype=torch.float32, device=device)

        train_ds = TensorDataset(to_tensor(X_train), to_tensor(y_train))
        train_loader = DataLoader(train_ds, batch_size=params.batch_size, shuffle=True)

        has_val = X_test.shape[0] > 0
        if has_val:
            val_ds = TensorDataset(to_tensor(X_test), to_tensor(y_test))
            val_loader = DataLoader(val_ds, batch_size=params.batch_size, shuffle=False)

        # ── Training loop ────────────────────────────────────────────────
        train_losses: list[float] = []
        val_losses:   list[float] = []

        for epoch in range(1, params.epochs + 1):
            model.train()
            epoch_train_loss = 0.0
            for xb, yb in train_loader:
                optimizer.zero_grad()
                pred = model(xb)
                loss = criterion(pred, yb)
                loss.backward()
                optimizer.step()
                epoch_train_loss += loss.item() * len(xb)
            avg_train = epoch_train_loss / len(X_train)
            train_losses.append(avg_train)

            if has_val:
                model.eval()
                with torch.no_grad():
                    epoch_val_loss = 0.0
                    for xb, yb in val_loader:
                        pred = model(xb)
                        epoch_val_loss += criterion(pred, yb).item() * len(xb)
                    avg_val = epoch_val_loss / len(X_test)
                val_losses.append(avg_val)
                logger.info("Epoch %3d/%d  train_loss=%.6f  val_loss=%.6f",
                            epoch, params.epochs, avg_train, avg_val)
            else:
                logger.info("Epoch %3d/%d  train_loss=%.6f", epoch, params.epochs, avg_train)

        # ── Evaluate helper ──────────────────────────────────────────────
        def evaluate(X: np.ndarray, y_scaled: np.ndarray) -> dict[str, float]:
            if X.shape[0] == 0:
                return {"r2": 0.0, "mape": 0.0, "n_samples": 0}
            model.eval()
            with torch.no_grad():
                y_pred_scaled = model(to_tensor(X)).cpu().numpy()
            y_pred = scaler_y.inverse_transform(y_pred_scaled)
            y_true = scaler_y.inverse_transform(y_scaled)
            r2 = float(r2_score(y_true, y_pred))
            mask = (y_true > 0.01).ravel()
            mape = (
                float(mean_absolute_percentage_error(y_true[mask], y_pred[mask]) * 100)
                if mask.sum() > 0 else 0.0
            )
            return {"r2": round(r2, 4), "mape": round(mape, 2), "n_samples": int(X.shape[0])}

        metrics = {
            "test":    evaluate(X_test,    y_test),
            "holdout": evaluate(X_holdout, y_holdout),
        }

        logger.info(
            "LSTMTrainerNode: metrics test=%s  holdout=%s",
            metrics["test"], metrics["holdout"],
        )

        # ── Save artifacts ───────────────────────────────────────────────
        os.makedirs(MODELS_DIR, exist_ok=True)
        run_id = str(uuid.uuid4())[:8]
        stem = f"{params.model_name}_{run_id}"

        model_path   = os.path.join(MODELS_DIR, f"{stem}.pt")
        arch_path    = os.path.join(MODELS_DIR, f"{stem}_arch.json")
        metrics_path = os.path.join(MODELS_DIR, f"{stem}_metrics.json")
        history_path = os.path.join(MODELS_DIR, f"{stem}_history.json")

        # State dict (CPU tensors)
        torch.save(model.state_dict(), model_path)

        # Architecture JSON (needed by predictor to reconstruct the module)
        arch = {
            "n_features":   n_features,
            "seq_length":   seq_length,
            "lstm_units":   params.lstm_units,
            "dropout":      params.dropout,
            "bidirectional": params.bidirectional,
            "sequences_artifact": sequences_path,
        }
        with open(arch_path, "w") as f:
            json.dump(arch, f, indent=2)

        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        history = {
            "train_loss": train_losses,
            "val_loss":   val_losses,
            "epochs":     list(range(1, params.epochs + 1)),
        }
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)

        logger.info("LSTMTrainerNode: saved model to %s", model_path)

        return {
            "model":         model_path,
            "metrics":       metrics,
            "artifact_path": model_path,
            "history":       history,
            "feature_names": feature_names,
        }
