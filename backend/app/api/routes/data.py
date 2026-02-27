"""
Generic data query endpoint for dynamic ``BaseDatasource`` datasources.

GET /api/v1/data/{key}
  Query any datasource registered via ``BaseDatasource`` (i.e. any ``ds_*.py``
  file in ``app/ingest/``).  Supports optional ``?state``, ``?county``,
  ``?year``, ``?skip``, and ``?limit`` query parameters.

GET /api/v1/data/{key}/distinct/{column}
  Return distinct values for a single column, with optional ``?state`` filter.
  Used by the frontend crop and state dropdowns.

These endpoints replace the per-domain route files (yields.py, weather.py, etc.).
"""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/data", tags=["data"])


class DataResponse(BaseModel):
    key: str
    data: list[dict[str, Any]]
    count: int


def _get_ds(key: str):
    from app.ingest.base import BaseDatasource
    ds = BaseDatasource._instances.get(key)
    if ds is None:
        raise HTTPException(
            status_code=404,
            detail=f"Datasource '{key}' not found. "
                   f"Known datasources: {list(BaseDatasource._instances.keys())}",
        )
    return ds


@router.get("/{key}/distinct/{column}")
def get_distinct_values(
    key: str,
    column: str,
    state: Optional[str] = Query(None),
) -> list[str]:
    """Return sorted distinct values for *column* in datasource *key*."""
    ds = _get_ds(key)
    col_names = [c.name for c in ds.columns]
    if column not in col_names:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not in datasource '{key}'.")

    from sqlalchemy import select, distinct
    from app.core.db import engine

    table = ds._get_table()
    q = select(distinct(table.c[column]))
    if state is not None and "state" in col_names:
        q = q.where(table.c["state"] == state)

    with engine.connect() as conn:
        rows = conn.execute(q).fetchall()

    return sorted({str(r[0]) for r in rows if r[0] is not None})


@router.get("/{key}", response_model=DataResponse)
def get_datasource_data(
    key: str,
    state:  Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    year:   Optional[int] = Query(None),
    skip:   int           = Query(default=0,    ge=0),
    limit:  int           = Query(default=1000, le=10000),
) -> DataResponse:
    """Query data for any ``BaseDatasource``-registered datasource."""
    ds = _get_ds(key)
    rows, total = ds.query(state=state, county=county, year=year, skip=skip, limit=limit)
    return DataResponse(key=key, data=rows, count=total)
