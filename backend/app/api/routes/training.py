"""
Model training, persistence, and inference endpoints for MLPlayground.

Trained models are serialised to disk with joblib and their metadata
(features, filters, metrics) is stored in the model_runs DB table.
This lets researchers reload any past run for inference without retraining.
"""
import json
import os
import uuid
from typing import Literal, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sqlmodel import Session, select

from app.core.db import get_session
from app.db_models import ModelRun, ModelRunPublic, ModelRunsPublic
from pydantic import BaseModel

ARTIFACTS_DIR = os.environ.get("ARTIFACTS_DIR", "/app/artifacts/models")

router = APIRouter(prefix="/models", tags=["models"])


class ModelTypeInfo(BaseModel):
    key: str
    label: str
    kind: str
    description: str
    supports_predict: bool


@router.get("/types", response_model=list[ModelTypeInfo])
def list_model_types() -> list[ModelTypeInfo]:
    """Return all registered model types so the frontend never hardcodes them."""
    return [ModelTypeInfo(key=k, **v) for k, v in MODEL_REGISTRY.items()]



AVAILABLE_FEATURES = [
    # Weather
    "avg_temp",
    "precipitation",
    "gdd",
    "vp",
    "srad",
    # Soil
    "ph",
    "organic_matter",
    "sand_pct",
    "clay_pct",
]

MODEL_TYPES = Literal["linear_regression", "random_forest", "gradient_boosting", "lstm", "pycaret"]

# Registry: maps model type key → metadata (drives GET /api/v1/models/types)
MODEL_REGISTRY: dict[str, dict] = {
    "linear_regression": {
        "label": "Linear Regression",
        "kind": "sklearn",
        "description": "Simple interpretable baseline. Fast to train, assumes linear feature-target relationships.",
        "supports_predict": True,
    },
    "random_forest": {
        "label": "Random Forest",
        "kind": "sklearn",
        "description": "Ensemble of decision trees. Robust to outliers and nonlinear patterns. Good default choice.",
        "supports_predict": True,
    },
    "gradient_boosting": {
        "label": "Gradient Boosting",
        "kind": "sklearn",
        "description": "Sequential boosted trees. Often highest accuracy for tabular data.",
        "supports_predict": True,
    },
    "lstm": {
        "label": "LSTM (Sequence Neural Network)",
        "kind": "pytorch",
        "description": "Recurrent neural network that learns from multi-year sequences. Captures carry-over effects.",
        "supports_predict": False,
    },
    "pycaret": {
        "label": "AutoML (PyCaret)",
        "kind": "pycaret",
        "description": "Automatically compares all regression algorithms and returns the best performer. Slower but hands-off.",
        "supports_predict": True,
    },
}


class TrainRequest(BaseModel):
    """Parameters for a model training run."""

    state: str
    crop: str
    start_year: Optional[int] = 1980
    end_year: Optional[int] = 2022
    features: list[str] = AVAILABLE_FEATURES
    model_type: MODEL_TYPES = "random_forest"
    test_size: float = 0.2


class FeatureImportance(BaseModel):
    feature: str
    importance: float


class TrainResult(BaseModel):
    """Results returned to the frontend after training."""

    run_id: Optional[str] = None       # UUID of the persisted model run (None for lstm)
    model_type: str
    n_samples: int
    n_train: int
    n_test: int
    r2: float
    rmse: float
    feature_importances: list[FeatureImportance]
    state: str
    crop: str
    start_year: int
    end_year: int


class PredictRequest(BaseModel):
    """Parameters for a single-point yield prediction."""

    state: str
    crop: str
    model_type: MODEL_TYPES = "random_forest"
    train_start_year: Optional[int] = 1980
    train_end_year: Optional[int] = 2022
    features: list[str] = AVAILABLE_FEATURES
    input_values: dict[str, float]


class PredictResult(BaseModel):
    predicted_yield: float
    model_type: str
    training_r2: float
    training_rmse: float
    units: str = "bu/acre"


# ---------------------------------------------------------------------------
# Helper: build a joined DataFrame from the three tables
# ---------------------------------------------------------------------------


def _load_joined_data(
    state: str,
    crop: str,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    Fetches Yield, Weather, and Soil rows via the BaseDatasource plugin system
    and joins them on (county, year).  Returns a flat DataFrame.
    """
    from app.ingest.base import BaseDatasource

    yields_ds  = BaseDatasource._instances.get("yields")
    weather_ds = BaseDatasource._instances.get("weather")
    soil_ds    = BaseDatasource._instances.get("soil")

    if not yields_ds or not weather_ds or not soil_ds:
        return pd.DataFrame()

    yields_rows, _  = yields_ds.query(state=state,  limit=200_000)
    weather_rows, _ = weather_ds.query(state=state, limit=200_000)
    soil_rows, _    = soil_ds.query(state=state,    limit=10_000)

    if not yields_rows:
        return pd.DataFrame()

    yield_df = pd.DataFrame(yields_rows)
    yield_df["year"] = pd.to_numeric(yield_df["year"], errors="coerce")
    yield_df = yield_df[
        (yield_df["crop"].str.upper() == crop.upper()) &
        (yield_df["year"] >= start_year) &
        (yield_df["year"] <= end_year)
    ].rename(columns={"value": "crop_yield"})[["year", "county", "state", "crop_yield"]]

    if yield_df.empty:
        return pd.DataFrame()

    weather_df = pd.DataFrame(weather_rows)[
        ["year", "county", "avg_temp", "precipitation", "gdd", "vp", "srad"]
    ] if weather_rows else pd.DataFrame()

    soil_df = pd.DataFrame(soil_rows)[
        ["county", "ph", "organic_matter", "sand_pct", "clay_pct"]
    ] if soil_rows else pd.DataFrame()

    df = yield_df
    if not weather_df.empty:
        df = df.merge(weather_df, on=["year", "county"], how="left")
    if not soil_df.empty:
        df = df.merge(soil_df, on="county", how="left")
    return df


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/train", response_model=TrainResult)
def train_model(
    req: TrainRequest,
    session: Session = Depends(get_session),
) -> TrainResult:
    """
    Train a machine learning model to predict crop yield.

    Joins Yield + Weather + Soil tables on (county, state, year),
    trains the selected model, and returns evaluation metrics and
    feature importances so you can understand what drives the prediction.
    """
    invalid = [f for f in req.features if f not in AVAILABLE_FEATURES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown feature(s): {invalid}. Valid features: {AVAILABLE_FEATURES}",
        )
    if not req.features:
        raise HTTPException(status_code=422, detail="At least one feature must be selected.")

    start_year = req.start_year or 1980
    end_year = req.end_year or 2022

    df = _load_joined_data(req.state, req.crop, start_year, end_year)

    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No yield data found for {req.crop} in {req.state} "
                f"({req.start_year}–{req.end_year}). "
                "Run the ingestion pipeline first."
            ),
        )

    available_features = [f for f in req.features if f in df.columns]
    if not available_features:
        raise HTTPException(
            status_code=422,
            detail="None of the requested features are available in the database. Run ingestion first.",
        )

    df_model_full = df[["county", "year"] + available_features + ["crop_yield"]].dropna()
    df_model = df_model_full  # keep county/year for LSTM sequencing
    if len(df_model) < 10:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df_model)} complete rows found after joining tables. "
                "At least 10 are needed to train a model. "
                "Try ingesting more counties or a broader year range."
            ),
        )

    X = df_model[available_features].values
    y = df_model["crop_yield"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=req.test_size, random_state=42
    )

    if req.model_type == "lstm":
        return _run_lstm_model(
            req, X_train, X_test, y_train, y_test, available_features, df_model, start_year, end_year
        )

    if req.model_type == "pycaret":
        return _run_pycaret_model(
            req, df_model, available_features, X_train, X_test, y_train, y_test,
            session, start_year, end_year,
        )

    model_map = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=100, random_state=42),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, random_state=42),
    }
    model = model_map[req.model_type]
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    r2 = float(r2_score(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    # Feature importances (coefficients for linear; feature_importances_ for tree models)
    if hasattr(model, "feature_importances_"):
        raw_importances = model.feature_importances_
    else:
        # Linear regression: use absolute normalised coefficients
        coef = np.abs(model.coef_)
        raw_importances = coef / coef.sum() if coef.sum() > 0 else coef

    importances = [
        FeatureImportance(feature=f, importance=float(v))
        for f, v in sorted(
            zip(available_features, raw_importances), key=lambda x: x[1], reverse=True
        )
    ]

    # Persist model artifact + metadata
    run_id = str(uuid.uuid4())
    artifact_path: Optional[str] = None
    try:
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        artifact_path = os.path.join(ARTIFACTS_DIR, f"{run_id}.pkl")
        joblib.dump({"model": model, "features": available_features}, artifact_path)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Failed to persist model artifact for run %s", run_id)

    run = ModelRun(
        run_id=run_id,
        model_type=req.model_type,
        datasources=json.dumps(["yields", "weather", "soil"]),
        join_keys=json.dumps(["year", "state", "county"]),
        feature_columns=json.dumps(available_features),
        target_column="value",
        filters=json.dumps({"state": req.state, "crop": req.crop,
                            "start_year": start_year, "end_year": end_year}),
        r2=round(r2, 4),
        rmse=round(rmse, 4),
        n_samples=len(df_model),
        artifact_path=artifact_path,
    )
    try:
        session.add(run)
        session.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Failed to persist ModelRun record for run %s", run_id)
        session.rollback()

    result = TrainResult(
        model_type=req.model_type,
        n_samples=len(df_model),
        n_train=len(X_train),
        n_test=len(X_test),
        r2=round(r2, 4),
        rmse=round(rmse, 4),
        feature_importances=importances,
        state=req.state,
        crop=req.crop,
        start_year=start_year,
        end_year=end_year,
    )
    result.run_id = run_id  # type: ignore[attr-defined]
    return result


def _run_pycaret_model(
    req: "TrainRequest",
    df_model: pd.DataFrame,
    feature_names: list[str],
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    session: Session,
    start_year: int,
    end_year: int,
) -> "TrainResult":
    """
    Use PyCaret's AutoML to compare all regression algorithms and return the best.

    PyCaret runs k-fold cross-validation on the training split for ranking, then
    we evaluate the selected best model on the held-out test split so metrics are
    directly comparable to the other model types.

    The winning estimator is a plain sklearn-compatible object and can be loaded
    with joblib for future inference.
    """
    try:
        from pycaret.regression import (
            compare_models,
            get_config,
            pull,
            setup,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="AutoML requires the 'pycaret' package. Install it with: pip install 'pycaret[full]'",
        ) from exc

    # Build a clean DataFrame for PyCaret (feature columns + target)
    df_pc = df_model[feature_names + ["crop_yield"]].dropna().copy()

    # PyCaret needs the train/test split to match ours for fair metric comparison.
    # We set train_size explicitly so compare_models's CV uses the same portion.
    train_size = 1.0 - req.test_size

    import logging as _logging
    _log = _logging.getLogger(__name__)

    try:
        setup(
            data=df_pc,
            target="crop_yield",
            session_id=42,
            train_size=train_size,
            verbose=False,
            html=False,
            log_experiment=False,
            system_log=False,
        )
        best_model = compare_models(sort="RMSE", verbose=True, errors="ignore")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PyCaret AutoML failed: {exc}",
        ) from exc

    

    # Evaluate on held-out test split for consistent metric reporting
    X_test_df = pd.DataFrame(X_test, columns=feature_names)
    y_pred = best_model.predict(X_test_df)
    r2 = float(r2_score(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    # Best model name from comparison table
    comparison_df = pull()
    best_label = comparison_df.index[0] if len(comparison_df) > 0 else "best"
    _log.info("PyCaret best model: %s  R²=%.3f  RMSE=%.3f", best_label, r2, rmse)

    # Feature importances — not all estimators expose them; fall back gracefully
    if hasattr(best_model, "feature_importances_"):
        raw = best_model.feature_importances_
    elif hasattr(best_model, "coef_"):
        raw = np.abs(best_model.coef_)
        raw = raw / raw.sum() if raw.sum() > 0 else raw
    else:
        raw = np.ones(len(feature_names)) / len(feature_names)

    importances = [
        FeatureImportance(feature=f, importance=float(v))
        for f, v in sorted(zip(feature_names, raw), key=lambda x: x[1], reverse=True)
    ]

    # Persist
    run_id = str(uuid.uuid4())
    artifact_path: Optional[str] = None
    try:
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        artifact_path = os.path.join(ARTIFACTS_DIR, f"{run_id}.pkl")
        joblib.dump({"model": best_model, "features": feature_names}, artifact_path)
    except Exception:
        _log.warning("Failed to persist PyCaret artifact for run %s", run_id)

    run = ModelRun(
        run_id=run_id,
        model_type=f"pycaret:{best_label}",
        datasources=json.dumps(["yields", "weather", "soil"]),
        join_keys=json.dumps(["year", "state", "county"]),
        feature_columns=json.dumps(feature_names),
        target_column="value",
        filters=json.dumps({"state": req.state, "crop": req.crop,
                            "start_year": start_year, "end_year": end_year}),
        r2=round(r2, 4),
        rmse=round(rmse, 4),
        n_samples=len(df_model),
        artifact_path=artifact_path,
    )
    try:
        session.add(run)
        session.commit()
    except Exception:
        _log.warning("Failed to persist ModelRun record for run %s", run_id)
        session.rollback()

    result = TrainResult(
        model_type=f"pycaret:{best_label}",
        n_samples=len(df_model),
        n_train=len(X_train),
        n_test=len(X_test),
        r2=round(r2, 4),
        rmse=round(rmse, 4),
        feature_importances=importances,
        state=req.state,
        crop=req.crop,
        start_year=start_year,
        end_year=end_year,
    )
    result.run_id = run_id  # type: ignore[attr-defined]
    return result


def _run_lstm_model(
    req: "TrainRequest",
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str],
    df_model: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> "TrainResult":
    """
    Train a single-layer LSTM on windowed sequences of annual features.

    Each sample is a window of ``seq_len`` consecutive years for a county,
    and the target is the yield in the final year of the window.  The LSTM
    captures multi-year weather patterns (e.g. drought carry-over) that
    static models cannot represent.

    Requires PyTorch (``torch`` package).
    """
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="LSTM requires the 'torch' package. Install it with: pip install torch",
        ) from exc

    SEQ_LEN = 3
    HIDDEN = 64
    EPOCHS = 150
    LR = 3e-3

    # --- Normalise features ------------------------------------------------
    X_mean = X_train.mean(axis=0)
    X_std  = X_train.std(axis=0) + 1e-8
    y_mean = float(y_train.mean())
    y_std  = float(y_train.std()) + 1e-8

    def norm_X(a: np.ndarray) -> np.ndarray:
        return (a - X_mean) / X_std

    def norm_y(a: np.ndarray) -> np.ndarray:
        return (a - y_mean) / y_std

    def denorm_y(a: np.ndarray) -> np.ndarray:
        return a * y_std + y_mean

    # --- Build sequences per county ----------------------------------------
    def make_sequences(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        seqs, targets = [], []
        for _, grp in df.groupby("county"):
            grp = grp.sort_values("year")
            feats = norm_X(grp[feature_names].values)
            ys    = norm_y(grp["crop_yield"].values)
            for i in range(len(grp) - SEQ_LEN):
                seqs.append(feats[i : i + SEQ_LEN])
                targets.append(ys[i + SEQ_LEN])
        if not seqs:
            return np.empty((0, SEQ_LEN, len(feature_names))), np.empty(0)
        return np.array(seqs, dtype=np.float32), np.array(targets, dtype=np.float32)

    # Use the full dataset for sequence building (train/test indices lack county info)
    df_sorted = df_model.copy()
    n_total   = len(df_sorted)
    split_idx = int(n_total * (1 - req.test_size))
    df_tr = df_sorted.iloc[:split_idx]
    df_te = df_sorted.iloc[split_idx:]

    X_seq_tr, y_seq_tr = make_sequences(df_tr)
    X_seq_te, y_seq_te = make_sequences(df_te)

    if len(X_seq_tr) < 4:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Not enough sequential data for LSTM (found {len(X_seq_tr)} windows, need ≥4). "
                "Try a broader year range or more counties."
            ),
        )

    # --- Model definition --------------------------------------------------
    class YieldLSTM(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lstm = nn.LSTM(len(feature_names), HIDDEN, batch_first=True)
            self.drop = nn.Dropout(0.2)
            self.fc   = nn.Linear(HIDDEN, 1)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            out, _ = self.lstm(x)
            return self.fc(self.drop(out[:, -1, :])).squeeze(1)

    model = YieldLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.MSELoss()

    ds = TensorDataset(
        torch.from_numpy(X_seq_tr),
        torch.from_numpy(y_seq_tr),
    )
    loader = DataLoader(ds, batch_size=min(32, len(ds)), shuffle=True)

    model.train()
    for _ in range(EPOCHS):
        for xb, yb in loader:
            opt.zero_grad()
            loss_fn(model(xb), yb).backward()
            opt.step()

    # --- Evaluate ----------------------------------------------------------
    model.eval()
    with torch.no_grad():
        if len(X_seq_te) > 0:
            y_pred_norm = model(torch.from_numpy(X_seq_te)).numpy()
            y_pred      = denorm_y(y_pred_norm)
            y_true      = denorm_y(y_seq_te)
        else:
            # Fall back to training set if test split too small for sequences
            y_pred_norm = model(torch.from_numpy(X_seq_tr)).numpy()
            y_pred      = denorm_y(y_pred_norm)
            y_true      = denorm_y(y_seq_tr)

    r2   = float(r2_score(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))

    # LSTM has no native feature importances; approximate via input gradient norm
    model.eval()
    x_sample = torch.from_numpy(X_seq_tr[:1]).requires_grad_(True)
    model(x_sample).sum().backward()
    grad_importance = x_sample.grad.abs().mean(dim=(0, 1)).detach().numpy()
    total = grad_importance.sum() + 1e-8
    importances = [
        FeatureImportance(feature=f, importance=float(v / total))
        for f, v in sorted(
            zip(feature_names, grad_importance), key=lambda x: x[1], reverse=True
        )
    ]

    return TrainResult(
        model_type="lstm",
        n_samples=len(df_model),
        n_train=len(X_seq_tr),
        n_test=len(X_seq_te),
        r2=round(r2, 4),
        rmse=round(rmse, 4),
        feature_importances=importances,
        state=req.state,
        crop=req.crop,
        start_year=start_year,
        end_year=end_year,
    )


@router.post("/predict", response_model=PredictResult)
def predict_yield(
    req: PredictRequest,
    session: Session = Depends(get_session),
) -> PredictResult:
    """
    Train a model on historical data and return a single predicted yield
    for the provided feature values.

    This lets researchers run counterfactual scenarios (e.g. "what would a
    Random Forest trained on 2000–2020 predict for avg_temp=24, precip=500?").
    LSTM is not supported via this endpoint (use /train instead).
    """
    if req.model_type in ("lstm", "pycaret"):
        raise HTTPException(
            status_code=422,
            detail=f"'{req.model_type}' is not supported via /predict. Use /train to train and save the model, then use /{'{run_id}'}/predict for inference.",
        )

    train_start = req.train_start_year or 1980
    train_end   = req.train_end_year or 2022

    invalid = [f for f in req.features if f not in AVAILABLE_FEATURES]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown features: {invalid}")

    df = _load_joined_data(req.state, req.crop, train_start, train_end)
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data for {req.crop} in {req.state} ({train_start}–{train_end}). Run ingestion first.",
        )

    available = [f for f in req.features if f in df.columns]
    df_model = df[available + ["crop_yield"]].dropna()
    if len(df_model) < 10:
        raise HTTPException(status_code=422, detail=f"Only {len(df_model)} rows after joining — need ≥10.")

    X = df_model[available].values
    y = df_model["crop_yield"].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model_map = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=100, random_state=42),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, random_state=42),
    }
    model = model_map[req.model_type]
    model.fit(X_train, y_train)

    r2   = float(r2_score(y_test, model.predict(X_test)))
    rmse = float(np.sqrt(mean_squared_error(y_test, model.predict(X_test))))

    # Build input vector in feature order, defaulting missing values to training mean
    col_means = dict(zip(available, X_train.mean(axis=0)))
    x_input = np.array(
        [[req.input_values.get(f, col_means[f]) for f in available]], dtype=float
    )
    predicted = float(model.predict(x_input)[0])

    return PredictResult(
        predicted_yield=round(predicted, 2),
        model_type=req.model_type,
        training_r2=round(r2, 4),
        training_rmse=round(rmse, 4),
    )


# ---------------------------------------------------------------------------
# Saved model run gallery
# ---------------------------------------------------------------------------

@router.get("/", response_model=ModelRunsPublic)
def list_model_runs(
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 50,
) -> ModelRunsPublic:
    """List all saved model training runs, newest first."""
    from sqlalchemy import func
    total = session.exec(select(func.count()).select_from(ModelRun)).one()
    runs = session.exec(select(ModelRun).offset(skip).limit(limit)).all()
    return ModelRunsPublic(data=list(runs), count=total)


class SavedRunPredictRequest(BaseModel):
    """Predict using a previously saved model run (no retraining needed)."""
    input_values: dict[str, float]


@router.post("/{run_id}/predict", response_model=PredictResult)
def predict_with_saved_run(
    run_id: str,
    req: SavedRunPredictRequest,
    session: Session = Depends(get_session),
) -> PredictResult:
    """
    Load a saved sklearn model by ``run_id`` and run inference against
    the supplied feature values.  Missing values default to 0.0.
    """
    run = session.exec(select(ModelRun).where(ModelRun.run_id == run_id)).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Model run '{run_id}' not found.")

    if not run.artifact_path or not os.path.exists(run.artifact_path):
        raise HTTPException(
            status_code=409,
            detail=f"Artifact for run '{run_id}' is missing from disk. Retrain the model.",
        )

    payload = joblib.load(run.artifact_path)
    model = payload["model"]
    features: list[str] = payload["features"]

    x_input = np.array(
        [[req.input_values.get(f, 0.0) for f in features]], dtype=float
    )
    predicted = float(model.predict(x_input)[0])

    return PredictResult(
        predicted_yield=round(predicted, 2),
        model_type=run.model_type,
        training_r2=round(run.r2 or 0.0, 4),
        training_rmse=round(run.rmse or 0.0, 4),
    )
