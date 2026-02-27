"""
PSA (Precision Sustainable Agriculture) daily weather datasource.

Fetches daily weather variables from https://weather.covercrop-data.org/daily
for a given county/state/year range and persists them to the ``weather_psa``
table.

This file is the complete implementation — no other files need to be touched.
"""
import logging
from typing import Optional

import pandas as pd
import requests

from app.ingest.base import BaseDatasource, Column

logger = logging.getLogger(__name__)


class WeatherPSA(BaseDatasource):
    key         = "weather_psa"
    label       = "PSA Daily Weather"
    description = "Daily weather variables from the Precision Sustainable Agriculture API."

    columns = [
        Column("year",                       int),
        Column("state",                      str),
        Column("county",                     str),
        Column("source",                     str),
        Column("date",                       str),
        Column("lat",                        float),
        Column("lon",                        float),
        Column("precipitation",              float),
        Column("longwave_radiation",         float),
        Column("shortwave_radiation",        float),
        Column("potential_energy",           float),
        Column("potential_evaporation",      float),
        Column("convective_precipitation",   float),
        Column("min_air_temperature",        float),
        Column("max_air_temperature",        float),
        Column("avg_air_temperature",        float),
        Column("min_humidity",               float),
        Column("max_humidity",               float),
        Column("avg_humidity",               float),
        Column("min_relative_humidity",      float),
        Column("max_relative_humidity",      float),
        Column("avg_relative_humidity",      float),
        Column("min_pressure",               float),
        Column("max_pressure",               float),
        Column("avg_pressure",               float),
        Column("min_zonal_wind_speed",       float),
        Column("max_zonal_wind_speed",       float),
        Column("avg_zonal_wind_speed",       float),
        Column("min_meridional_wind_speed",  float),
        Column("max_meridional_wind_speed",  float),
        Column("avg_meridional_wind_speed",  float),
        Column("min_wind_speed",             float),
        Column("max_wind_speed",             float),
        Column("avg_wind_speed",             float),
    ]

    scope_params = [
        {
            "name": "states",
            "type": "string_list",
            "label": "States",
            "placeholder": "e.g. North Carolina, Iowa",
            "default": ["North Carolina"],
        },
        {"name": "start_year", "type": "integer", "label": "Start Year", "default": 2020},
        {"name": "end_year",   "type": "integer", "label": "End Year",   "default": 2022},
    ]

    def fetch(
        self,
        county: str,
        state: str,
        start_year: int,
        end_year: int,
    ) -> Optional[pd.DataFrame]:
        logger.info("Fetching PSA weather for %s, %s (%d–%d)…", county, state, start_year, end_year)

        params = {
            "email":    "jd@ex.com",
            "location": f"{county} county {state}",
            "start":    f"{start_year}-01-01",
            "end":      f"{end_year}-12-31",
            "gddbase":  "10",
            "gddmin":   "10",
            "gddmax":   "30",
            "output":   "json",
        }
        response = requests.get(
            "https://weather.covercrop-data.org/daily",
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        df = pd.DataFrame(response.json())
        if df.empty:
            return df

        date_col = pd.to_datetime(df["date"])
        df["year"]   = date_col.dt.year
        df["county"] = county
        df["state"]  = state
        df["source"] = self.key
        df["lat"]    = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"]    = pd.to_numeric(df["lon"], errors="coerce")

        col_names = [c.name for c in self.columns]
        return df[[c for c in col_names if c in df.columns]]
