"""
=============================================================================
NEW DATASOURCE TEMPLATE — MLPlayground
=============================================================================

HOW TO USE
----------
1. Copy this file to a new name starting with "ds_", e.g.  ds_ndvi.py
2. Fill in every TODO section below.
3. Save the file.  That's it — no other files need to be changed.

WHAT HAPPENS AUTOMATICALLY
---------------------------
• The datasource appears in the Explore page and the Ingest form.
• A database table is created on first use (no migration needed).
• A query endpoint is available at  GET /api/v1/data/<key>
• The ingest pipeline can fetch and store data when triggered.
=============================================================================
"""
from typing import Optional

import pandas as pd
import requests

from app.ingest.base import BaseDatasource, Column


class MyDataSource(BaseDatasource):       # TODO: rename this class

    # ------------------------------------------------------------------
    # TODO 1 — Identity
    # ------------------------------------------------------------------
    key         = "my_datasource"         # TODO: unique machine-readable key
    label       = "My Data Source"        # TODO: human-readable label shown in UI
    description = "Short description."    # TODO: one sentence describing the source

    # ------------------------------------------------------------------
    # TODO 2 — Schema
    # Define every column your fetch() method returns.
    # Supported types: int, float, str
    # The first three (year, state, county) are strongly recommended.
    # ------------------------------------------------------------------
    columns = [
        Column("year",      int),
        Column("state",     str),
        Column("county",    str),
        Column("my_metric", float),   # TODO: replace / extend with your columns
    ]

    # ------------------------------------------------------------------
    # TODO 3 (optional) — Ingest scope parameters
    # These drive the Ingest form in the UI.  Remove or adjust as needed.
    # ------------------------------------------------------------------
    scope_params = [
        {
            "name": "states",
            "type": "string_list",
            "label": "States",
            "default": ["North Carolina"],
        },
        {"name": "start_year", "type": "integer", "label": "Start Year", "default": 1980},
        {"name": "end_year",   "type": "integer", "label": "End Year",   "default": 2022},
    ]

    # ------------------------------------------------------------------
    # TODO 4 — Fetch logic  ← the only method you must implement
    # ------------------------------------------------------------------
    def fetch(
        self,
        county: str,
        state: str,
        start_year: int,
        end_year: int,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data for one county/state over a year range.

        Return a DataFrame whose columns match self.columns above.
        Return None or an empty DataFrame if no data is available.
        Raise an exception if the request fails — the runner will log it
        and continue to the next county.
        """
        # Example: call a REST API
        response = requests.get(
            "https://api.example.com/data",
            params={
                "county":      county,
                "state":       state,
                "start":       start_year,
                "end":         end_year,
            },
            timeout=30,
        )
        response.raise_for_status()

        df = pd.DataFrame(response.json())
        df["year"]   = df["year"].astype(int)
        df["county"] = county
        df["state"]  = state
        return df[[c.name for c in self.columns]]
