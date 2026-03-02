"""
USDA SSURGO soil properties datasource plugin.

Fetches area-weighted topsoil properties for each county from the USDA
Soil Data Mart (SDM) API.  Year range is ignored — soil data is static.
"""
import logging
from typing import Optional

import pandas as pd

from app.ingest.base import BaseDatasource, Column

logger = logging.getLogger(__name__)


class SoilDatasource(BaseDatasource):
    key         = "soil"
    label       = "Soil Properties"
    description = "County-level topsoil properties (area-weighted) from USDA SSURGO via the SDM API."

    columns = [
        Column("state",          str),
        Column("county",         str),
        Column("ph",             float),
        Column("organic_matter", float),
        Column("sand_pct",       float),
        Column("clay_pct",       float),
    ]

    # Soil is time-invariant: no year range needed.
    scope_params = [
        {"name": "county", "type": "string", "label": "County", "placeholder": "e.g. Wake",            "default": ""},
        {"name": "state",  "type": "string", "label": "State",  "placeholder": "e.g. North Carolina", "default": "North Carolina"},
    ]

    def fetch(
        self,
        county: str,
        state: str,
        **kwargs,  # absorbs start_year/end_year if passed by the ingest runner
    ) -> Optional[pd.DataFrame]:
        from app.ingest._daymet_helpers import fetch_ssurgo_soil

        return fetch_ssurgo_soil(county, state)
