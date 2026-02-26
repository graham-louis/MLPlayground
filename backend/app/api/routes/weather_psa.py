from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, and_
from app.core.db import get_session
from app.db_models import WeatherPSA, WeatherPSAPublic, WeathersPSAPublic

router = APIRouter(prefix="/weather-psa", tags=["weather-psa"])


@router.get("/", response_model=WeathersPSAPublic)
def get_weather_psa(
    session: Session = Depends(get_session),
    state: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = Query(default=1000, le=10000),
) -> WeathersPSAPublic:
    query = select(WeatherPSA)
    conditions = []
    if state:
        conditions.append(WeatherPSA.state == state)
    if county:
        conditions.append(WeatherPSA.county == county)
    if year:
        conditions.append(WeatherPSA.year == year)
    if conditions:
        query = query.where(and_(*conditions))

    all_results = session.exec(select(WeatherPSA).where(and_(*conditions)) if conditions else select(WeatherPSA)).all()
    results = session.exec(query.offset(skip).limit(limit)).all()
    return WeathersPSAPublic(data=results, count=len(all_results))
