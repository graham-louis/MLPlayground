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

MODEL_TYPES = Literal["linear_regression", "random_forest", "gradient_boosting"]


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
    # Validate requested features
    invalid = [f for f in req.features if f not in AVAILABLE_FEATURES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown feature(s): {invalid}. Valid features: {AVAILABLE_FEATURES}",
        )
    if not req.features:
        raise HTTPException(status_code=422, detail="At least one feature must be selected.")

    df = _load_joined_data(session, req.state, req.crop, req.start_year or 1980, req.end_year or 2022)

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

    df_model = df[available_features + ["crop_yield"]].dropna()
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
        start_year=req.start_year or 1980,
        end_year=req.end_year or 2022,
    )
