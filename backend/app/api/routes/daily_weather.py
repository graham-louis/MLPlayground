"""
Daily weather API route.

Exposes the daily_weather table for the Data Explorer frontend tab.
Supports filtering by state, county, and year range.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.db import get_session
from app.models import DailyWeather, DailyWeatherPublic
from pydantic import BaseModel

router = APIRouter(prefix="/daily-weather", tags=["daily-weather"])


class DailyWeathersPublic(BaseModel):
    data: list[DailyWeatherPublic]
    count: int


@router.get("/", response_model=DailyWeathersPublic)
def get_daily_weather(
    state: Optional[str] = None,
    county: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    limit: int = 500,
    session: Session = Depends(get_session),
) -> DailyWeathersPublic:
    """
    Return daily weather rows filtered by state, county, and/or year range.
    Results are capped at ``limit`` rows (default 500) to keep response sizes manageable.
    """
    query = select(DailyWeather)
    if state:
        query = query.where(DailyWeather.state == state)
    if county:
        query = query.where(DailyWeather.county == county)
    if start_year:
        query = query.where(DailyWeather.year >= start_year)
    if end_year:
        query = query.where(DailyWeather.year <= end_year)

    rows = session.exec(query.limit(limit)).all()
    return DailyWeathersPublic(
        data=[DailyWeatherPublic.model_validate(r) for r in rows],
        count=len(rows),
    )
