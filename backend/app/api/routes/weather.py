from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, and_
from app.core.db import get_session
from app.models import Weather, WeatherPublic, WeathersPublic

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/", response_model=WeathersPublic)
def get_weather(
    session: Session = Depends(get_session),
    state: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = Query(default=1000, le=10000),
) -> WeathersPublic:
    query = select(Weather)
    conditions = []
    if state:
        conditions.append(Weather.state == state)
    if county:
        conditions.append(Weather.county == county)
    if year:
        conditions.append(Weather.year == year)
    if conditions:
        query = query.where(and_(*conditions))

    all_results = session.exec(select(Weather).where(and_(*conditions)) if conditions else select(Weather)).all()
    results = session.exec(query.offset(skip).limit(limit)).all()
    return WeathersPublic(data=results, count=len(all_results))
