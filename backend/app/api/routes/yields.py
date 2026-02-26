from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, and_
from app.core.db import get_session
from app.db_models import Yield, YieldPublic, YieldsPublic

router = APIRouter(prefix="/yields", tags=["yields"])


@router.get("/", response_model=YieldsPublic)
def get_yields(
    session: Session = Depends(get_session),
    state: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = Query(default=1000, le=10000),
) -> YieldsPublic:
    query = select(Yield)
    conditions = []
    if state:
        conditions.append(Yield.state == state)
    if crop:
        conditions.append(Yield.crop == crop)
    if start_year:
        conditions.append(Yield.year >= start_year)
    if end_year:
        conditions.append(Yield.year <= end_year)
    if conditions:
        query = query.where(and_(*conditions))

    count = session.exec(select(Yield).where(and_(*conditions)) if conditions else select(Yield)).all()
    results = session.exec(query.offset(skip).limit(limit)).all()
    return YieldsPublic(data=results, count=len(count))


@router.get("/crops", response_model=list[str], tags=["yields"])
def get_crops(
    session: Session = Depends(get_session),
    state: Optional[str] = Query(None),
) -> list[str]:
    query = select(Yield.crop).distinct()
    if state:
        query = query.where(Yield.state == state)
    results = session.exec(query).all()
    return sorted(set(r for r in results if r))


@router.get("/states", response_model=list[str], tags=["yields"])
def get_states(session: Session = Depends(get_session)) -> list[str]:
    results = session.exec(select(Yield.state).distinct()).all()
    return sorted(set(r for r in results if r))
