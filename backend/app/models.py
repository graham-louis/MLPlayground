from typing import Optional
from sqlmodel import Field, SQLModel


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


# Generic message
class Message(SQLModel):
    message: str
