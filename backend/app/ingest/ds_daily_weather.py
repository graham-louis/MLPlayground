"""
Daymet daily weather datasource plugin.

Fetches complete daily weather time-series per county from the Daymet API.
Suitable for LSTM and other time-series models.
"""
import logging
from typing import Optional

import pandas as pd

from app.ingest.base import BaseDatasource, Column

logger = logging.getLogger(__name__)


class DailyWeatherDatasource(BaseDatasource):
    key         = "daily_weather"
    label       = "Daily Weather"
    description = "Daily weather variables from the Daymet API. Suitable for time-series models such as LSTM."

    columns = [
        Column("year",        int),
        Column("day_of_year", int),
        Column("date",        str),
        Column("state",       str),
        Column("county",      str),
        Column("tmax",        float),
        Column("tmin",        float),
        Column("prcp",        float),
        Column("srad",        float),
        Column("vp",          float),
        Column("dayl",        float),
    ]

    def fetch(
        self,
        county: str,
        state: str,
        start_year: int,
        end_year: int,
    ) -> Optional[pd.DataFrame]:
        from app.ingest._daymet_helpers import fetch_daymet_daily

        return fetch_daymet_daily(county, state, start_year, end_year)
