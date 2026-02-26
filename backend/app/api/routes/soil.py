from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, and_
from app.core.db import get_session
from app.db_models import Soil, SoilPublic, SoilsPublic

router = APIRouter(prefix="/soil", tags=["soil"])


@router.get("/", response_model=SoilsPublic)
def get_soil(
    session: Session = Depends(get_session),
    state: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = Query(default=1000, le=10000),
) -> SoilsPublic:
    query = select(Soil)
    conditions = []
    if state:
        conditions.append(Soil.state == state)
    if county:
        conditions.append(Soil.county == county)
    if conditions:
        query = query.where(and_(*conditions))

    all_results = session.exec(select(Soil).where(and_(*conditions)) if conditions else select(Soil)).all()
    results = session.exec(query.offset(skip).limit(limit)).all()
    return SoilsPublic(data=results, count=len(all_results))
