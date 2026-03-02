"""
USDA NASS crop yield datasource plugin.

Fetches annual county-level crop yield data from the USDA NASS QuickStats API.
Requires NASS_API_KEY to be set in settings.
"""
import logging
from typing import Optional

import pandas as pd
import requests

from app.ingest.base import BaseDatasource, Column

logger = logging.getLogger(__name__)


class YieldsDatasource(BaseDatasource):
    key         = "yields"
    label       = "Crop Yields"
    description = "Annual county-level crop yield data from USDA NASS QuickStats."

    columns = [
        Column("year",         int),
        Column("state",        str),
        Column("county",       str),
        Column("crop",         str),
        Column("value",        float),
        Column("unit",         str),
        Column("district",     str),
        Column("county_ansi",  str),
    ]

    scope_params = [
        {
            "name": "state",
            "type": "string",
            "label": "State Name",
            "description": "Full US state name or abbreviation, e.g. 'NORTH CAROLINA' or 'NC'.",
            "default": "NORTH CAROLINA",
        },
        {
            "name": "county",
            "type": "string",
            "label": "County (optional)",
            "description": "County name, e.g. 'WAKE'. Leave empty to fetch all counties.",
            "default": "",
        },
        {
            "name": "start_year",
            "type": "integer",
            "label": "Start Year",
            "default": 1990,
        },
        {
            "name": "end_year",
            "type": "integer",
            "label": "End Year",
            "default": 2024,
        },
    ]

    def fetch(
        self,
        county: str = "",
        state: str = "NORTH CAROLINA",
        start_year: int = 1990,
        end_year: int = 2024,
    ) -> Optional[pd.DataFrame]:
        from app.core.config import settings

        api_key = settings.NASS_API_KEY
        if not api_key or api_key == "YOUR_API_KEY":
            raise RuntimeError(
                "YieldsDatasource: NASS_API_KEY is not configured. "
                "Set it in your .env file or environment and restart."
            )

        county = (county or "").strip()
        logger.info(
            "Fetching NASS yields for county=%r state=%s (%d–%d)…",
            county or "<all>", state, start_year, end_year,
        )
        params: dict = {
            "key": api_key,
            "source_desc": "SURVEY",
            "sector_desc": "CROPS",
            "group_desc": "FIELD CROPS",
            "statisticcat_desc": "YIELD",
            "unit_desc": "BU / ACRE",
            "agg_level_desc": "COUNTY",
            "state_name": state.upper(),
            "year__LE": end_year,
            "year__GE": start_year,
            "format": "JSON",
        }
        # Only filter by county when one is specified — omitting it returns all counties
        if county:
            params["county_name"] = county.upper()
        try:
            response = requests.get(
                "https://quickstats.nass.usda.gov/api/api_GET/",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("NASS API request failed for %s, %s: %s", county, state, exc)
            return None

        data = response.json().get("data", [])
        if not data:
            logger.warning("No yield data returned from NASS for %s, %s.", county, state)
            return None

        df = pd.DataFrame(data)
        df["Value"] = df["Value"].astype(str).str.replace(",", "", regex=False)
        df["value"] = pd.to_numeric(df["Value"], errors="coerce")
        df.dropna(subset=["value"], inplace=True)

        result = pd.DataFrame({
            "year": df["year"].astype(int),
            "state": state,
            "county": df.get("county_name", pd.Series([county] * len(df))).str.title(),
            "crop": df.get("commodity_desc", pd.Series([""] * len(df))),
            "value": df["value"],
            "unit": df.get("unit_desc", pd.Series([None] * len(df))),
            "district": df.get("asd_desc", pd.Series([None] * len(df))),
            "county_ansi": df.get("county_ansi", pd.Series([None] * len(df))).astype(str),
        })
        logger.info("NASS yields fetched: %d rows for %s, %s.", len(result), county, state)
        return result
