from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from db.models import Yield
import os

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db")
engine = create_engine(DATABASE_URL)

@router.get("/yields/")
def get_yields(
    state: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    year: Optional[int] = Query(None)
):
    with Session(engine) as session:
        query = select(Yield)
        if state:
            query = query.where(Yield.state == state)
        if crop:
            query = query.where(Yield.crop == crop)
        if year:
            query = query.where(Yield.year == year)
        results = session.execute(query).scalars().all()
        # Convert ORM objects to dicts
        return [
            {
                "id": y.id,
                "year": y.year,
                "state": y.state,
                "district": y.district,
                "county": y.county,
                "county_ansi": y.county_ansi,
                "crop": y.crop,
                "value": y.value,
                "unit": y.unit
            }
            for y in results
        ]
