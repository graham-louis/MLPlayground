"""
Datasource registry for MLPlayground.

Every ingest module calls ``DATASOURCE_REGISTRY.register(...)`` at import
time so that the platform can discover all available data sources without
any hardcoded lists.  The registry is read by:

  - GET /api/v1/datasources/   — drives the Explore page tabs
  - POST /api/v1/ingest/run    — dispatches the correct fetch function
  - The Model page feature picker  — lists available columns

Usage (in an ingest module)::

    from app.ingest.registry import DATASOURCE_REGISTRY

    DATASOURCE_REGISTRY.register(
        key="my_source",
        label="My Data Source",
        endpoint="/api/v1/my-source/",
        columns=["year", "state", "county", "my_metric"],
        scope_params=[
            {"name": "states",      "type": "string_list", "label": "States"},
            {"name": "start_year",  "type": "integer",     "label": "Start Year", "default": 1980},
            {"name": "end_year",    "type": "integer",     "label": "End Year",   "default": 2022},
        ],
        fetch_fn=fetch_and_transform,
    )
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DatasourceEntry:
    """Metadata and callable for a single registered datasource."""

    def __init__(
        self,
        key: str,
        label: str,
        endpoint: str,
        columns: list[str],
        scope_params: list[dict[str, Any]],
        fetch_fn: Optional[Callable[..., Any]] = None,
        upsert_fn: Optional[Callable[..., Any]] = None,
        description: str = "",
    ) -> None:
        self.key = key
        self.label = label
        self.endpoint = endpoint
        self.columns = columns
        self.scope_params = scope_params
        self.fetch_fn = fetch_fn
        self.upsert_fn = upsert_fn
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "endpoint": self.endpoint,
            "columns": self.columns,
            "scope_params": self.scope_params,
            "description": self.description,
        }


class DatasourceRegistry:
    """Central registry for all datasource modules."""

    def __init__(self) -> None:
        self._entries: dict[str, DatasourceEntry] = {}

    def register(
        self,
        key: str,
        label: str,
        endpoint: str,
        columns: list[str],
        scope_params: list[dict[str, Any]],
        fetch_fn: Optional[Callable[..., Any]] = None,
        upsert_fn: Optional[Callable[..., Any]] = None,
        description: str = "",
    ) -> None:
        if key in self._entries:
            logger.warning("DatasourceRegistry: overwriting existing entry for key=%r", key)
        self._entries[key] = DatasourceEntry(
            key=key,
            label=label,
            endpoint=endpoint,
            columns=columns,
            scope_params=scope_params,
            fetch_fn=fetch_fn,
            upsert_fn=upsert_fn,
            description=description,
        )
        logger.debug("DatasourceRegistry: registered datasource key=%r", key)

    def get(self, key: str) -> Optional[DatasourceEntry]:
        return self._entries.get(key)

    def list(self) -> list[DatasourceEntry]:
        return list(self._entries.values())

    def keys(self) -> list[str]:
        return list(self._entries.keys())


# Singleton used throughout the application
DATASOURCE_REGISTRY = DatasourceRegistry()

# ---------------------------------------------------------------------------
# Register the bundled agriculture example-domain datasources.
# Each registration lives here so there is a single source of truth.
# New datasource modules can import DATASOURCE_REGISTRY and call .register()
# in their own module body — they just need to be imported before the API
# starts (they're imported by the ingest runner, which is imported at startup).
# ---------------------------------------------------------------------------

_COMMON_SCOPE = [
    {
        "name": "states",
        "type": "string_list",
        "label": "States",
        "placeholder": "e.g. North Carolina, Iowa",
        "default": ["North Carolina"],
    },
    {
        "name": "start_year",
        "type": "integer",
        "label": "Start Year",
        "default": 1980,
    },
    {
        "name": "end_year",
        "type": "integer",
        "label": "End Year",
        "default": 2022,
    },
]

DATASOURCE_REGISTRY.register(
    key="yields",
    label="Crop Yields",
    endpoint="/api/v1/yields/",
    columns=["year", "state", "county", "crop", "value", "unit"],
    scope_params=_COMMON_SCOPE,
    description="Annual county-level crop yield data from USDA NASS QuickStats.",
)

DATASOURCE_REGISTRY.register(
    key="weather",
    label="Annual Weather",
    endpoint="/api/v1/weather/",
    columns=["year", "state", "county", "avg_temp", "precipitation", "gdd", "vp", "srad"],
    scope_params=_COMMON_SCOPE,
    description="Annual aggregated weather variables from the Daymet API.",
)

DATASOURCE_REGISTRY.register(
    key="soil",
    label="Soil Properties",
    endpoint="/api/v1/soil/",
    columns=["state", "county", "ph", "organic_matter", "sand_pct", "clay_pct"],
    scope_params=[
        {
            "name": "states",
            "type": "string_list",
            "label": "States",
            "placeholder": "e.g. North Carolina, Iowa",
            "default": ["North Carolina"],
        },
    ],
    description="County-level soil properties from USDA SSURGO.",
)

DATASOURCE_REGISTRY.register(
    key="daily_weather",
    label="Daily Weather",
    endpoint="/api/v1/daily-weather/",
    columns=["year", "day_of_year", "date", "state", "county", "tmax", "tmin", "prcp", "srad", "vp", "dayl"],
    scope_params=_COMMON_SCOPE,
    description="Daily weather variables from the Daymet API. Required for time-series models such as LSTM.",
)
