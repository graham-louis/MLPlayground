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


# Generic message
class Message(SQLModel):
    message: str
