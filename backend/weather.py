from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from db.models import Weather
import os

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db")
engine = create_engine(DATABASE_URL)

@router.get("/weather/")
def get_weather(
    state: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    year: Optional[int] = Query(None)
):
    with Session(engine) as session:
        query = select(Weather)
        if state:
            query = query.where(Weather.state == state)
        if county:
            query = query.where(Weather.county == county)
        if year:
            query = query.where(Weather.year == year)
        results = session.execute(query).scalars().all()
        return [
            {
                "id": w.id,
                "year": w.year,
                "state": w.state,
                "county": w.county,
                "avg_temp": w.avg_temp,
                "precipitation": w.precipitation,
                "vp": w.vp,
                "srad": w.srad,
                "gdd": w.gdd
                # Add more fields as needed
            }
            for w in results
        ]
