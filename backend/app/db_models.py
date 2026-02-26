from typing import Optional
from sqlmodel import Field, SQLModel
import uuid as _uuid
from datetime import datetime as _datetime


# --- Yield Models ---
class YieldBase(SQLModel):
    year: int
    state: str
    district: Optional[str] = None
    county: str
    county_ansi: Optional[str] = None
    crop: str
    value: float
    unit: Optional[str] = None


class Yield(YieldBase, table=True):
    __tablename__ = "yields"
    id: Optional[int] = Field(default=None, primary_key=True)


class YieldPublic(YieldBase):
    id: int


class YieldsPublic(SQLModel):
    data: list[YieldPublic]
    count: int


# --- Weather Models ---
class WeatherBase(SQLModel):
    year: int
    state: str
    county: str
    avg_temp: Optional[float] = None
    precipitation: Optional[float] = None
    vp: Optional[float] = None
    srad: Optional[float] = None
    gdd: Optional[float] = None


class Weather(WeatherBase, table=True):
    __tablename__ = "weather"
    id: Optional[int] = Field(default=None, primary_key=True)


class WeatherPublic(WeatherBase):
    id: int


class WeathersPublic(SQLModel):
    data: list[WeatherPublic]
    count: int


# --- Soil Models ---
class SoilBase(SQLModel):
    state: str
    county: str
    ph: Optional[float] = None
    organic_matter: Optional[float] = None
    sand_pct: Optional[float] = None
    clay_pct: Optional[float] = None


class Soil(SoilBase, table=True):
    __tablename__ = "soil"
    id: Optional[int] = Field(default=None, primary_key=True)


class SoilPublic(SoilBase):
    id: int


class SoilsPublic(SQLModel):
    data: list[SoilPublic]
    count: int


# --- Daily Weather Models ---
class DailyWeatherBase(SQLModel):
    year: int
    day_of_year: int
    date: str           # ISO date string, e.g. "1980-01-01"
    state: str
    county: str
    tmax: Optional[float] = None    # °C
    tmin: Optional[float] = None    # °C
    prcp: Optional[float] = None    # mm
    srad: Optional[float] = None    # W/m²
    vp: Optional[float] = None      # Pa
    dayl: Optional[float] = None    # seconds of daylight


class DailyWeather(DailyWeatherBase, table=True):
    __tablename__ = "daily_weather"
    id: Optional[int] = Field(default=None, primary_key=True)


class DailyWeatherPublic(DailyWeatherBase):
    id: int


# --- Model Run (persisted training artifact) ---

class ModelRunBase(SQLModel):
    run_id: str                             # UUID string
    model_type: str
    datasources: str                        # JSON list, e.g. '["yields","weather","soil"]'
    join_keys: str                          # JSON list, e.g. '["year","state","county"]'
    feature_columns: str                    # JSON list
    target_column: str
    filters: str                            # JSON object, e.g. '{"state":"Iowa","crop":"CORN"}'
    r2: Optional[float] = None
    rmse: Optional[float] = None
    n_samples: Optional[int] = None
    artifact_path: Optional[str] = None    # path to .pkl file on disk
    created_at: str = Field(
        default_factory=lambda: _datetime.utcnow().isoformat()
    )


class ModelRun(ModelRunBase, table=True):
    __tablename__ = "model_runs"
    id: Optional[int] = Field(default=None, primary_key=True)


class ModelRunPublic(ModelRunBase):
    id: int


class ModelRunsPublic(SQLModel):
    data: list[ModelRunPublic]
    count: int

# --- Weather PSA Models ---
class WeatherPSABase(SQLModel):
    year: int
    state: str
    county: str
    source: str = "weather_psa"
    date: str           # ISO date string, e.g. "1980-01-01"
    lat: Optional[float] = None
    lon: Optional[float] = None
    precipitation: Optional[float] = None
    longwave_radiation: Optional[float] = None
    shortwave_radiation: Optional[float] = None
    potential_energy: Optional[float] = None
    potential_evaporation: Optional[float] = None
    convective_precipitation: Optional[float] = None
    min_air_temperature: Optional[float] = None
    max_air_temperature: Optional[float] = None
    avg_air_temperature: Optional[float] = None
    min_humidity: Optional[float] = None
    max_humidity: Optional[float] = None
    avg_humidity: Optional[float] = None
    min_relative_humidity: Optional[float] = None
    max_relative_humidity: Optional[float] = None
    avg_relative_humidity: Optional[float] = None
    min_pressure: Optional[float] = None
    max_pressure: Optional[float] = None
    avg_pressure: Optional[float] = None
    min_zonal_wind_speed: Optional[float] = None
    max_zonal_wind_speed: Optional[float] = None
    avg_zonal_wind_speed: Optional[float] = None
    min_meridional_wind_speed: Optional[float] = None
    max_meridional_wind_speed: Optional[float] = None
    avg_meridional_wind_speed: Optional[float] = None
    min_wind_speed: Optional[float] = None
    max_wind_speed: Optional[float] = None
    avg_wind_speed: Optional[float] = None

class WeatherPSA(WeatherPSABase, table=True):
    __tablename__ = "weather_psa"
    id: Optional[int] = Field(default=None, primary_key=True)

class WeatherPSAPublic(WeatherPSABase):
    id: int

class WeathersPSAPublic(SQLModel):
    data: list[WeatherPSA]
    count: int

# Generic message
class Message(SQLModel):
    message: str
