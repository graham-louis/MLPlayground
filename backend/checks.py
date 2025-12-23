from sqlalchemy import select
from db.models import Soil, Weather, Yield
from sqlalchemy.orm import Session
from typing import Optional


def yield_exists(session: Session, county: str, state: str, start: Optional[int] = None, end: Optional[int] = None) -> bool:
    """Return True if any Yield rows exist for the given county/state and optional year range."""
    conditions = [Yield.county == county, Yield.state == state]
    if start is not None:
        conditions.append(Yield.year >= start)
    if end is not None:
        conditions.append(Yield.year <= end)
    q = select(Yield).where(*conditions).limit(1)
    return session.execute(q).first() is not None


def weather_exists(session: Session, county: str, state: str, start: Optional[int] = None, end: Optional[int] = None) -> bool:
    """Return True if any Weather rows exist for the given county/state and optional year range."""
    conditions = [Weather.county == county, Weather.state == state]
    if start is not None:
        conditions.append(Weather.year >= start)
    if end is not None:
        conditions.append(Weather.year <= end)
    q = select(Weather).where(*conditions).limit(1)
    return session.execute(q).first() is not None


def soil_exists(session: Session, county: str, state: str) -> bool:
    q = select(Soil).where(Soil.county == county, Soil.state == state).limit(1)
    return session.execute(q).first() is not None