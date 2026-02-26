"""
=============================================================================
NEW DATASOURCE TEMPLATE — MLPlayground
=============================================================================

This file is a copy-paste starting point for adding a new data source.
Every section that needs your input is marked with "# TODO".

HOW TO USE THIS FILE
1. Copy it to a new name, e.g.:  satellite_ndvi.py
2. Work through every # TODO comment below.
3. Follow the "What to do next" guide at the bottom of this file.

WHAT THIS TEMPLATE DOES
It shows you exactly how to write a Python function that fetches data
from an external source and returns it as a standard table (DataFrame)
that MLPlayground can store and display.

You do NOT need to understand FastAPI, SQLAlchemy, or React.
You only need to fill in the TODO sections in this one file,
then follow the 4 follow-up steps described at the bottom.

EXAMPLE USE CASE
Imagine you want to add NDVI (satellite vegetation index) data from NASA.
The comments below use that as a running example.
=============================================================================
"""

# ---------------------------------------------------------------------------
# IMPORTS  (leave these alone unless you need extra libraries)
# ---------------------------------------------------------------------------
import logging
from typing import Optional

import pandas as pd
import requests

from app.ingest.registry import DATASOURCE_REGISTRY


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TODO 1 — Name your data source
# ---------------------------------------------------------------------------
# Replace "MyDataSource" with a short name for your source.
# Example: "SatelliteNDVI", "DroughtIndex", "PestPressure"

DATASOURCE_NAME = "WeatherPSA"   # TODO: change this

# ---------------------------------------------------------------------------
# TODO 2 — Describe your data source
# ---------------------------------------------------------------------------
# This text shows up in the UI and documentation.

DATASOURCE_DESCRIPTION = (
    "Weather data from Precision Sustainable Agriculture"
)   # TODO: change this

# ---------------------------------------------------------------------------
# TODO 3 — Define the columns your data returns
# ---------------------------------------------------------------------------
# List every column your function will return.
# The first four ("year", "state", "county", "source") are REQUIRED.
# Add your own domain columns after them.
#
# Example for NDVI:
#   DATASOURCE_COLUMNS = ["year", "state", "county", "source",
#                          "ndvi_mean", "ndvi_min", "ndvi_max"]

DATASOURCE_COLUMNS: list[str] = [
    "year",
    "state",
    "county",
    "source",
    "date",
    "lat",
    "lon", 
    "precipitation",
    "longwave_radiation",
    "shortwave_radiation",
    "potential_energy",
    "potential_evaporation",
    "convective_precipitation",
    "min_air_temperature",
    "max_air_temperature",
    "avg_air_temperature",
    "min_humidity",
    "max_humidity",
    "avg_humidity",
    "min_relative_humidity",
    "max_relative_humidity",
    "avg_relative_humidity",
    "min_pressure",
    "max_pressure",
    "avg_pressure",
    "min_zonal_wind_speed",
    "max_zonal_wind_speed",
    "avg_zonal_wind_speed",
    "min_meridional_wind_speed",
    "max_meridional_wind_speed",
    "avg_meridional_wind_speed",
    "min_wind_speed",
    "max_wind_speed",
    "avg_wind_speed",
]


# ---------------------------------------------------------------------------
# MAIN FETCH FUNCTION — this is the only function you must implement
# ---------------------------------------------------------------------------

def fetch_and_transform(
    county_name: str,
    state_name: str,
    start_year: int,
    end_year: int,
) -> Optional[pd.DataFrame]:
    """
    Fetch data for a single county/state over a range of years.

    Parameters
    ----------
    county_name : str
        The name of the county, e.g. "Wake".
    state_name : str
        The full state name, e.g. "North Carolina".
    start_year : int
        First year to fetch (inclusive).
    end_year : int
        Last year to fetch (inclusive).

    Returns
    -------
    pd.DataFrame
        A table with columns matching DATASOURCE_COLUMNS.
        Return None or an empty DataFrame if no data is available.

    Notes
    -----
    • The runner will call this function once per county, per state.
    • Any exception you raise will be caught and logged — the pipeline
      will continue with the next county.
    • Keep network calls efficient: fetch multiple years in one request
      where the API supports it.
    """
    logger.info(
        "Fetching %s data for %s, %s (%d–%d)...",
        DATASOURCE_NAME, county_name, state_name, start_year, end_year,
    )

    # TODO 4 — Replace this block with your actual data fetching logic.
    #
    # You have three common options:
    #
    # OPTION A — Call a REST API
    # --------------------------
    url = "https://weather.covercrop-data.org/daily"
    location = f"{county_name} county {state_name}"
    params = {
        "email": "jd@ex.com",
        "location": f"{county_name} county {state_name}",
        "start": f"{start_year}-01-01",
        "end": f"{end_year}-12-31",
        "gddbase": "10",
        "gddmin": "10",
        "gddmax": "30",
        "output": "json",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()            # raises an error if request failed
    data = response.json()    # adapt to the API's JSON structure
    df = pd.DataFrame(data)
    
    date = pd.to_datetime(df["date"])
    df["year"] = date.dt.year
    df["county"] = county_name
    df["state"] = state_name
    df["lat"] = pd.to_numeric(df["lat"])
    df["lon"] = pd.to_numeric(df["lon"])
    df["source"] = DATASOURCE_NAME
    # df = df.dropna(subset=["my_metric"])   # drop rows where your key metric is missing
    # return df[DATASOURCE_COLUMNS]          # return only the declared columns
    return df[DATASOURCE_COLUMNS]

def upsert_weather_psa_to_db(df: pd.DataFrame):
    from app.db_models import WeatherPSA
    from app.core.db import engine
    from sqlmodel import Session, select

    if df is None or df.empty:
        logger.debug("No weather data to upsert.")
        return

    with Session(engine) as session:
        for _, row in df.iterrows():
            obj = session.exec(
                select(WeatherPSA).where(
                    WeatherPSA.year == int(row["year"]),
                    WeatherPSA.date == row["date"],
                    WeatherPSA.county == row["county"],
                    WeatherPSA.state == row["state"],
                )
            ).first()
            if obj is None:
                obj = WeatherPSA(year=int(row["year"]), date=row["date"], county=row["county"], state=row["state"])
                obj.source = row.get("source")
                obj.lat = row.get("lat")
                obj.lon = row.get("lon")
                obj.precipitation = row.get("precipitation")
                obj.longwave_radiation = row.get("longwave_radiation")
                obj.shortwave_radiation = row.get("shortwave_radiation")
                obj.potential_energy = row.get("potential_energy")
                obj.potential_evaporation = row.get("potential_evaporation")
                obj.convective_precipitation = row.get("convective_precipitation")
                obj.min_air_temperature = row.get("min_air_temperature")
                obj.max_air_temperature = row.get("max_air_temperature")
                obj.avg_air_temperature = row.get("avg_air_temperature")
                obj.min_humidity = row.get("min_humidity")
                obj.max_humidity = row.get("max_humidity")
                obj.avg_humidity = row.get("avg_humidity")
                obj.min_relative_humidity = row.get("min_relative_humidity")
                obj.max_relative_humidity = row.get("max_relative_humidity")
                obj.avg_relative_humidity = row.get("avg_relative_humidity")
                obj.min_pressure = row.get("min_pressure")
                obj.max_pressure = row.get("max_pressure")
                obj.avg_pressure = row.get("avg_pressure")
                obj.min_zonal_wind_speed = row.get("min_zonal_wind_speed")
                obj.max_zonal_wind_speed = row.get("max_zonal_wind_speed")
                obj.avg_zonal_wind_speed = row.get("avg_zonal_wind_speed")
                obj.min_meridional_wind_speed = row.get("min_meridional_wind_speed")
                obj.max_meridional_wind_speed = row.get("max_meridional_wind_speed")
                obj.avg_meridional_wind_speed = row.get("avg_meridional_wind_speed")
                obj.min_wind_speed = row.get("min_wind_speed")
                obj.max_wind_speed = row.get("max_wind_speed")
                obj.avg_wind_speed = row.get("avg_wind_speed")
            session.add(obj)
        session.commit()
        logger.info("Upserted %d weather rows for %s.", len(df), df.iloc[0]["county"])


# Register the data source in the global registry — this makes it available in the UI and API.
DATASOURCE_REGISTRY.register(
    key="weather_psa",
    label="Weather PSA",
    endpoint="/api/v1/weather-psa/",
    columns=["year",
    "state",
    "county",
    "source",
    "date",
    "lat",
    "lon", 
    "precipitation",
    "longwave_radiation",
    "shortwave_radiation",
    "potential_energy",
    "potential_evaporation",
    "convective_precipitation",
    "min_air_temperature",
    "max_air_temperature",
    "avg_air_temperature",
    "min_humidity",
    "max_humidity",
    "avg_humidity",
    "min_relative_humidity",
    "max_relative_humidity",
    "avg_relative_humidity",
    "min_pressure",
    "max_pressure",
    "avg_pressure",
    "min_zonal_wind_speed",
    "max_zonal_wind_speed",
    "avg_zonal_wind_speed",
    "min_meridional_wind_speed",
    "max_meridional_wind_speed",
    "avg_meridional_wind_speed",
    "min_wind_speed",
    "max_wind_speed",
    "avg_wind_speed"],
    scope_params=[
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
            "default": 2020,
        },
        {
            "name": "end_year",
            "type": "integer",
            "label": "End Year",
            "default": 2022,
        },
    ],
    description="Weather variables from the PSA API. Required for time-series models such as LSTM.",
    fetch_fn=fetch_and_transform, 
    upsert_fn=upsert_weather_psa_to_db
)

