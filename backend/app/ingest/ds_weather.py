"""
Daymet annual growing-season weather datasource plugin.

Fetches Daymet daily weather and aggregates to growing-season (May–Sep)
annual summaries per county.
"""
import logging
from typing import Optional

import pandas as pd

from app.ingest.base import BaseDatasource, Column

logger = logging.getLogger(__name__)


class WeatherDatasource(BaseDatasource):
    key         = "weather"
    label       = "Annual Weather"
    description = "Annual growing-season weather aggregates (May–Sep) from the Daymet API."

    columns = [
        Column("year",          int),
        Column("state",         str),
        Column("county",        str),
        Column("avg_temp",      float),
        Column("precipitation", float),
        Column("gdd",           float),
        Column("vp",            float),
        Column("srad",          float),
    ]

    scope_params = [
        {"name": "county",     "type": "string",  "label": "County",     "placeholder": "e.g. Wake",             "default": ""},
        {"name": "state",      "type": "string",  "label": "State",      "placeholder": "e.g. North Carolina",  "default": "North Carolina"},
        {"name": "start_year", "type": "integer", "label": "Start Year", "default": 1980},
        {"name": "end_year",   "type": "integer", "label": "End Year",   "default": 2022},
    ]

    def fetch(
        self,
        county: str,
        state: str,
        start_year: int,
        end_year: int,
    ) -> Optional[pd.DataFrame]:
        from app.ingest._daymet_helpers import fetch_daymet_annual

        return fetch_daymet_annual(county, state, start_year, end_year)
