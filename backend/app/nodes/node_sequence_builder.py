"""Sequence Builder node — convert tabular DataFrames to LSTM-ready sequences.

Accepts the three temporal splits (train / test / holdout) produced by
``TemporalSplitNode`` and transforms them into sliding-window, 3-D NumPy
arrays of shape ``(n_samples, seq_length, n_features)`` suitable for
PyTorch LSTM training.

Key design decisions
--------------------
* Scalers (MinMaxScaler for features *and* target) are fitted **exclusively**
  on the training split, then applied to test and holdout — no future leakage.
* Sequences are built **per year** so that no window crosses a year boundary.
  This mirrors the Streamlit lab behaviour and prevents the model from seeing
  data from year Y+1 while "predicting" a day in year Y.
* All arrays and both scalers are serialized together as a single joblib
  artifact so that downstream nodes (trainer, predictor) can share a
  self-consistent state without re-fitting scaling logic.

Artifact layout (joblib-pickled dict)
--------------------------------------
::

    {
        "X_train":       np.ndarray  # (n, seq_len, n_features)
        "y_train":       np.ndarray  # (n, 1)
        "X_test":        np.ndarray  # (m, seq_len, n_features)
        "y_test":        np.ndarray  # (m, 1)
        "X_holdout":     np.ndarray  # (k, seq_len, n_features)
        "y_holdout":     np.ndarray  # (k, 1)
        "scaler_x":      MinMaxScaler
        "scaler_y":      MinMaxScaler
        "feature_names": list[str]
        "target_column": str
        "seq_length":    int
        "n_features":    int
    }
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)

ARTIFACTS_BASE: str = os.environ.get("ARTIFACTS_BASE", "/app/artifacts")


class SequenceBuilderNode(BaseNode):
    node_id = "sequence_builder"
    display_name = "Sequence Builder"
    description = (
        "Convert train / test / holdout DataFrames into sliding-window LSTM sequences. "
        "Fits MinMaxScaler on train only (no leakage). Sequences are built per year to "
        "prevent cross-year contamination. Saves arrays + scalers as a single artifact."
    )
    category = "Modeling"

    inputs = [
        IOSlot(name="train",   type=IOTypes.DATAFRAME),
        IOSlot(name="test",    type=IOTypes.DATAFRAME),
        IOSlot(name="holdout", type=IOTypes.DATAFRAME, required=False),
    ]
    outputs = [
        IOSlot(name="artifact_path", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        target_column: str = Field(
            default="soil_moisture",
            description="Name of the target / label column.",
        )
        feature_columns: list[str] = Field(
            default=[],
            description=(
                "Feature columns to use as inputs.  Leave empty to use all numeric "
                "columns except the target."
            ),
        )
        seq_length: int = Field(
            default=30,
            ge=3,
            le=365,
            description="Number of consecutive time steps per sequence window.",
        )
        year_column: str = Field(
            default="Year",
            description=(
                "Column that identifies the year of each row.  Used to prevent "
                "sequences from crossing year boundaries.  If blank, a single "
                "contiguous sequence is built across the whole split."
            ),
        )

    params = Params

    # ------------------------------------------------------------------
    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        from sklearn.preprocessing import MinMaxScaler
        import joblib

        train_df:   pd.DataFrame = inputs["train"]
        test_df:    pd.DataFrame = inputs["test"]
        holdout_df: pd.DataFrame = inputs.get("holdout", pd.DataFrame())

        # ── Resolve feature columns ──────────────────────────────────────
        numeric_cols = train_df.select_dtypes(include="number").columns.tolist()
        year_col = params.year_column if params.year_column in train_df.columns else None

        excluded = {params.target_column}
        if year_col:
            excluded.add(year_col)

        if params.feature_columns:
            feature_cols = [c for c in params.feature_columns if c in train_df.columns]
            missing = [c for c in params.feature_columns if c not in train_df.columns]
            if missing:
                logger.warning("SequenceBuilderNode: feature columns not found and skipped: %s", missing)
        else:
            feature_cols = [c for c in numeric_cols if c not in excluded]

        if not feature_cols:
            raise ValueError(
                "SequenceBuilderNode: no feature columns resolved. "
                f"target='{params.target_column}', available={list(train_df.columns)}"
            )

        if params.target_column not in train_df.columns:
            raise ValueError(
                f"SequenceBuilderNode: target column '{params.target_column}' not found. "
                f"Available: {list(train_df.columns)}"
            )

        logger.info(
            "SequenceBuilderNode: %d features, seq_length=%d, year_col=%s",
            len(feature_cols), params.seq_length, year_col,
        )

        # ── Fit scalers on training data only ───────────────────────────
        train_clean = train_df[feature_cols + [params.target_column]].fillna(0)

        scaler_x = MinMaxScaler()
        scaler_y = MinMaxScaler()
        scaler_x.fit(train_clean[feature_cols])
        scaler_y.fit(train_clean[[params.target_column]])

        # ── Sequence generator ───────────────────────────────────────────
        def make_sequences(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
            """Build (X, y) sequence arrays from a DataFrame.

            Iterates year-by-year when *year_col* is present to prevent
            sequences from crossing year boundaries.
            """
            if df is None or len(df) == 0:
                return np.empty((0, params.seq_length, len(feature_cols))), np.empty((0, 1))

            xs: list[np.ndarray] = []
            ys: list[np.ndarray] = []

            groups = df[year_col].unique() if year_col and year_col in df.columns else [None]

            for grp in groups:
                df_grp = df[df[year_col] == grp].copy() if grp is not None else df.copy()
                df_grp = df_grp[feature_cols + [params.target_column]].fillna(0)

                if len(df_grp) <= params.seq_length:
                    continue

                x_scaled = scaler_x.transform(df_grp[feature_cols])
                y_scaled = scaler_y.transform(df_grp[[params.target_column]])

                for i in range(len(x_scaled) - params.seq_length):
                    xs.append(x_scaled[i : i + params.seq_length])
                    ys.append(y_scaled[i + params.seq_length])

            if not xs:
                return np.empty((0, params.seq_length, len(feature_cols))), np.empty((0, 1))

            return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)

        X_train, y_train     = make_sequences(train_df)
        X_test,  y_test      = make_sequences(test_df)
        X_holdout, y_holdout = make_sequences(holdout_df) if len(holdout_df) > 0 else (
            np.empty((0, params.seq_length, len(feature_cols)), dtype=np.float32),
            np.empty((0, 1), dtype=np.float32),
        )

        logger.info(
            "SequenceBuilderNode: X_train=%s  X_test=%s  X_holdout=%s",
            X_train.shape, X_test.shape, X_holdout.shape,
        )

        if X_train.shape[0] == 0:
            raise ValueError(
                "SequenceBuilderNode: training split produced 0 sequences. "
                f"Try reducing seq_length (currently {params.seq_length}) or check "
                "that the train DataFrame has enough consecutive rows per year."
            )

        # ── Persist artifact ──────────────────────────────────────────────
        artifact = {
            "X_train":       X_train,
            "y_train":       y_train,
            "X_test":        X_test,
            "y_test":        y_test,
            "X_holdout":     X_holdout,
            "y_holdout":     y_holdout,
            "scaler_x":      scaler_x,
            "scaler_y":      scaler_y,
            "feature_names": feature_cols,
            "target_column": params.target_column,
            "seq_length":    params.seq_length,
            "n_features":    len(feature_cols),
        }

        out_dir = os.path.join(ARTIFACTS_BASE, "sequences")
        os.makedirs(out_dir, exist_ok=True)
        run_id = str(uuid.uuid4())
        artifact_path = os.path.join(out_dir, f"{run_id}.pkl")
        joblib.dump(artifact, artifact_path)
        logger.info("SequenceBuilderNode: saved artifact to %s", artifact_path)

        return {"artifact_path": artifact_path}
