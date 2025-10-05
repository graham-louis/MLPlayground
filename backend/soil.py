from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from db.models import Soil
import os

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db")
engine = create_engine(DATABASE_URL)

@router.get("/soil/")
def get_soil(
    state: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    district: Optional[str] = Query(None)
):
    with Session(engine) as session:
        query = select(Soil)
        if state:
            query = query.where(Soil.state == state)
        if county:
            query = query.where(Soil.county == county)
        if district:
            query = query.where(Soil.district == district)
        results = session.execute(query).scalars().all()
        return [
            {
                "id": s.id,
                "state": s.state,
                "district": s.district,
                "county": s.county,
                "county_ansi": s.county_ansi,
                "ph": s.ph,
                "organic_matter": s.organic_matter,
                "sand_pct": s.sand_pct,
                "silt_pct": s.silt_pct,
                "clay_pct": s.clay_pct,
                # Add more fields as needed
            }
            for s in results
        ]
