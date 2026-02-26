"""
Datasource registry API endpoint.

GET /api/v1/datasources/
  Returns the list of registered datasources with their metadata
  (key, label, endpoint, columns, scope_params).  The frontend uses this
  response to build the Explore tabs and the Ingest scope form dynamically
  — no hardcoded datasource names in the UI.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

# Import the registry (and trigger registration of the bundled datasources)
from app.ingest.registry import DATASOURCE_REGISTRY

router = APIRouter(prefix="/datasources", tags=["datasources"])


class DatasourceInfo(BaseModel):
    key: str
    label: str
    endpoint: str
    columns: list[str]
    scope_params: list[dict[str, Any]]
    description: str = ""


class DatasourcesResponse(BaseModel):
    data: list[DatasourceInfo]
    count: int


@router.get("/", response_model=DatasourcesResponse)
def list_datasources() -> DatasourcesResponse:
    """
    List all registered datasources.

    Returns metadata for each datasource:
    - **key**: machine-readable identifier (e.g. ``"yields"``)
    - **label**: human-readable name shown in the UI
    - **endpoint**: API path to query data (e.g. ``"/api/v1/yields/"``)
    - **columns**: list of column names returned by the endpoint
    - **scope_params**: filter dimensions the source supports (drives the Ingest form)
    - **description**: short text describing the source
    """
    entries = [DatasourceInfo(**e.to_dict()) for e in DATASOURCE_REGISTRY.list()]
    return DatasourcesResponse(data=entries, count=len(entries))
