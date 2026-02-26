"""
Model training endpoint for MLPlayground.

A researcher selects features and a target, picks a model type, and
this endpoint joins the Yield + Weather + Soil tables, trains the model,
and returns metrics + feature importances they can inspect immediately.
"""
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sqlmodel import Session, select

from app.core.db import get_session
from app.models import Soil, Weather, Yield, Message
from pydantic import BaseModel

router = APIRouter(prefix="/models", tags=["models"])

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

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

MODEL_TYPES = Literal["linear_regression", "random_forest", "gradient_boosting", "apsimx", "lstm"]


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


class DataSourceInfo(BaseModel):
    name: str
    description: str
    fields: list[str]


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
    session: Session,
    state: str,
    crop: str,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    Fetches Yield, Weather, and Soil rows for the requested scope and
    joins them on (county, state, year).  Returns a flat DataFrame.
    """
    yields = session.exec(
        select(Yield).where(
            Yield.state == state,
            Yield.crop == crop,
            Yield.year >= start_year,
            Yield.year <= end_year,
        )
    ).all()

    if not yields:
        return pd.DataFrame()

    yield_df = pd.DataFrame(
        [{"year": y.year, "county": y.county, "state": y.state, "crop_yield": y.value} for y in yields]
    )

    weather_rows = session.exec(
        select(Weather).where(
            Weather.state == state,
            Weather.year >= start_year,
            Weather.year <= end_year,
        )
    ).all()
    weather_df = pd.DataFrame(
        [
            {
                "year": w.year,
                "county": w.county,
                "avg_temp": w.avg_temp,
                "precipitation": w.precipitation,
                "gdd": w.gdd,
                "vp": w.vp,
                "srad": w.srad,
            }
            for w in weather_rows
        ]
    )

    soil_rows = session.exec(
        select(Soil).where(Soil.state == state)
    ).all()
    soil_df = pd.DataFrame(
        [
            {
                "county": s.county,
                "ph": s.ph,
                "organic_matter": s.organic_matter,
                "sand_pct": s.sand_pct,
                "clay_pct": s.clay_pct,
            }
            for s in soil_rows
        ]
    )

    # Join on (county, year) then (county) for soil
    df = yield_df.merge(weather_df, on=["year", "county"], how="left")
    df = df.merge(soil_df, on="county", how="left")
    return df


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/datasources", response_model=list[DataSourceInfo])
def get_datasources() -> list[DataSourceInfo]:
    """
    Returns metadata for every available data source.
    The frontend uses this to auto-populate the Data Explorer tabs.
    """
    return [
        DataSourceInfo(
            name="yields",
            description="Annual crop yield data (bu/acre) from USDA NASS QuickStats.",
            fields=["year", "state", "county", "crop", "value", "unit"],
        ),
        DataSourceInfo(
            name="weather",
            description="Growing-season weather aggregates from Daymet (NASA).",
            fields=["year", "state", "county", "avg_temp", "precipitation", "gdd", "vp", "srad"],
        ),
        DataSourceInfo(
            name="soil",
            description="Topsoil properties from SSURGO (USDA NRCS).",
            fields=["state", "county", "ph", "organic_matter", "sand_pct", "clay_pct"],
        ),
    ]


@router.get("/features", response_model=list[str])
def get_available_features() -> list[str]:
    """Returns the list of feature columns available for model training."""
    return AVAILABLE_FEATURES


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
    # Validate requested features (not applicable for ApsimX which uses its own inputs)
    if req.model_type != "apsimx":
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

    # ── ApsimX path ────────────────────────────────────────────────────────
    if req.model_type == "apsimx":
        return _run_apsimx_model(req, session, start_year, end_year)

    # ── sklearn / LSTM path ───────────────────────────────────────────────
    df = _load_joined_data(session, req.state, req.crop, start_year, end_year)

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

    return TrainResult(
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
    ApsimX is not supported via this endpoint (use /train instead).
    """
    if req.model_type in ("apsimx", "lstm"):
        raise HTTPException(
            status_code=422,
            detail=f"'{req.model_type}' is not supported via /predict. Use /train instead.",
        )

    train_start = req.train_start_year or 1980
    train_end   = req.train_end_year or 2022

    invalid = [f for f in req.features if f not in AVAILABLE_FEATURES]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown features: {invalid}")

    df = _load_joined_data(session, req.state, req.crop, train_start, train_end)
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


def _run_apsimx_model(
    req: "TrainRequest",
    session: Session,
    start_year: int,
    end_year: int,
) -> "TrainResult":
    """
    Run ApsimX simulations for each county in the requested state/crop/year range,
    compare simulated yields to observed USDA NASS yields, and return metrics.

    Weather and soil data are sourced from the DailyWeather and Soil DB tables.
    Run POST /api/v1/ingest/trigger-daily-weather to populate daily weather data
    before using this model type.

    ApsimX is a process-based crop simulator, not an ML model.  There is no
    train/test split — the simulator uses only weather and agronomic rules.
    R² and RMSE measure how well the physics model reproduces observed data.
    """
    from app.ingest.apsimx_runner import simulate_yields, CROP_CONFIG

    crop_upper = req.crop.upper()
    if crop_upper not in CROP_CONFIG:
        raise HTTPException(
            status_code=422,
            detail=(
                f"ApsimX has no template for crop '{req.crop}'. "
                f"Supported crops: {', '.join(CROP_CONFIG.keys())}."
            ),
        )

    # Fetch observed yields for the state
    obs_yields = session.exec(
        select(Yield).where(
            Yield.state == req.state,
            Yield.crop == req.crop,
            Yield.year >= start_year,
            Yield.year <= end_year,
        )
    ).all()

    if not obs_yields:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No observed yield data for {req.crop} in {req.state} "
                f"({start_year}–{end_year}). Run the ingestion pipeline first."
            ),
        )

    obs_df = pd.DataFrame([{"year": y.year, "county": y.county, "obs_yield": y.value} for y in obs_yields])

    counties = sorted(obs_df["county"].unique())
    all_sim: list[pd.DataFrame] = []

    for county in counties:
        try:
            sim_df = simulate_yields(
                county=county,
                crop=req.crop,
                start_year=start_year,
                end_year=end_year,
                session=session,
                state=req.state,
            )
            if sim_df is not None and not sim_df.empty:
                sim_df["county"] = county
                all_sim.append(sim_df)
        except Exception as exc:
            # Log and continue — one county failure doesn't abort the run
            import logging
            logging.getLogger(__name__).warning(
                "ApsimX simulation failed for %s, %s: %s", county, req.state, exc
            )

    if not all_sim:
        raise HTTPException(
            status_code=500,
            detail=(
                "ApsimX produced no output for any county. "
                "Check that APSIMX_BIN is set and the binary is executable, "
                "and that daily weather has been ingested via POST /api/v1/ingest/trigger-daily-weather."
            ),
        )

    sim_df_all = pd.concat(all_sim, ignore_index=True)

    # ApsimX yields are in kg/ha; NASS yields are in bu/acre (corn ≈ 6.28 kg/ha per bu/acre)
    CORN_KG_HA_PER_BU_ACRE = 62.77  # 1 bu/acre corn = 62.77 kg/ha
    sim_df_all["sim_yield_bu_ac"] = sim_df_all["simulated_yield_kg_ha"] / CORN_KG_HA_PER_BU_ACRE

    merged = obs_df.merge(sim_df_all[["year", "county", "sim_yield_bu_ac"]], on=["year", "county"], how="inner")

    if len(merged) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(merged)} matching year×county pairs between simulations and observations. "
                "Try a broader year range or ensure weather data covers the requested period."
            ),
        )

    y_obs = merged["obs_yield"].values
    y_sim = merged["sim_yield_bu_ac"].values

    r2 = float(r2_score(y_obs, y_sim))
    rmse = float(np.sqrt(mean_squared_error(y_obs, y_sim)))

    # For ApsimX there are no feature importances in the ML sense.
    # Return simulation statistics as informational "importances".
    sim_stats = [
        FeatureImportance(feature="sim_mean_yield_bu_ac", importance=round(float(np.mean(y_sim)), 2)),
        FeatureImportance(feature="obs_mean_yield_bu_ac", importance=round(float(np.mean(y_obs)), 2)),
        FeatureImportance(feature="counties_simulated", importance=float(len(counties))),
        FeatureImportance(feature="matched_county_years", importance=float(len(merged))),
    ]

    return TrainResult(
        model_type="apsimx",
        n_samples=len(merged),
        n_train=len(merged),
        n_test=0,
        r2=round(r2, 4),
        rmse=round(rmse, 4),
        feature_importances=sim_stats,
        state=req.state,
        crop=req.crop,
        start_year=start_year,
        end_year=end_year,
    )
