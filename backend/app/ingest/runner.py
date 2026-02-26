"""
Bulk ingestion runner for MLPlayground.

Ingestion is driven entirely by the USDA NASS API — no local CSV files.
The NASS_API_KEY setting must be set.

The list of states to ingest is read from the INGEST_STATES environment
variable (comma-separated, e.g. "North Carolina,Iowa,Illinois").
If INGEST_STATES is not set, a default set of states is used.
Year range defaults to 1980–2022 and can be overridden via
INGEST_START_YEAR and INGEST_END_YEAR.
"""
import logging
import os

import requests
from sqlmodel import Session, select

import pandas as pd
from app.core.config import settings
from app.core.db import engine
from app.ingest.weather_daymet import _validate_name, fetch_and_transform_weather, save_daily_weather_to_db
from app.ingest.yields_nass import fetch_and_transform_yield
from app.ingest.soil_ssurgo import fetch_and_transform_soil
from app.ingest.weather_psa import fetch_and_transform

logger = logging.getLogger(__name__)

DEFAULT_STATES = [
    "North Carolina",
    "Iowa",
    "Illinois",
    "Indiana",
    "Nebraska",
    "Minnesota",
    "Ohio",
    "Missouri",
    "South Dakota",
    "Kansas",
]


def get_counties_for_state(state_name: str) -> list[str]:
    """Queries the USDA SDM API to return all county names in a given state."""
    state_name = _validate_name(state_name.strip(), "state_name")
    logger.info("Fetching county list for %s...", state_name)
    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    query = f"SELECT areaname FROM sacatalog WHERE areaname LIKE '%, {state_name}'"
    try:
        response = requests.post(sdm_api_url, data={"FORMAT": "JSON", "QUERY": query}, timeout=30)
        response.raise_for_status()
        data = response.json().get("Table", [])
        if len(data) < 2:
            return []
        return sorted(row[0].split(" County,")[0] for row in data[1:])
    except requests.RequestException as exc:
        logger.error("Error fetching county list for %s: %s", state_name, exc)
        return []


def upsert_soil_to_db(df: pd.DataFrame) -> None:
    """Upserts soil features in a single session/transaction."""
    from app.db_models import Soil

    if df is None or df.empty:
        logger.debug("No soil data to upsert.")
        return

    with Session(engine) as session:
        for _, row in df.iterrows():
            obj = session.exec(
                select(Soil).where(Soil.county == row["County"], Soil.state == row["State"])
            ).first()
            if obj is None:
                obj = Soil(county=row["County"], state=row["State"])
            obj.ph = row["Soil_pH"]
            obj.organic_matter = row["OM_percent"]
            obj.sand_pct = row["PercentSand"]
            obj.clay_pct = row["PercentClay"]
            session.add(obj)
        session.commit()
        logger.info("Upserted soil data for %s, %s.", df.iloc[0]["County"], df.iloc[0]["State"])


def upsert_weather_to_db(df: pd.DataFrame) -> None:
    """Upserts annual weather rows in a single session/transaction."""
    from app.db_models import Weather

    if df is None or df.empty:
        logger.debug("No weather data to upsert.")
        return

    with Session(engine) as session:
        for _, row in df.iterrows():
            obj = session.exec(
                select(Weather).where(
                    Weather.year == int(row["Year"]),
                    Weather.county == row["County"],
                    Weather.state == row["State"],
                )
            ).first()
            if obj is None:
                obj = Weather(year=int(row["Year"]), county=row["County"], state=row["State"])
            obj.avg_temp = row.get("AvgTemp_C")
            obj.precipitation = row.get("TotalPrecip_mm")
            obj.gdd = row.get("TotalGDD")
            obj.vp = row.get("vp")
            obj.srad = row.get("srad")
            session.add(obj)
        session.commit()
        logger.info("Upserted %d weather rows for %s.", len(df), df.iloc[0]["County"])


def upsert_yield_to_db(df: pd.DataFrame) -> None:
    """Upserts annual yield rows in a single session/transaction."""
    from app.db_models import Yield

    if df is None or df.empty:
        logger.debug("No yield data to upsert.")
        return

    with Session(engine) as session:
        for _, row in df.iterrows():
            obj = session.exec(
                select(Yield).where(
                    Yield.year == int(row["Year"]),
                    Yield.county == row["County"],
                    Yield.state == row["State"],
                    Yield.crop == row.get("Crop"),
                )
            ).first()
            if obj is None:
                obj = Yield(
                    year=int(row["Year"]),
                    county=row["County"],
                    state=row["State"],
                    crop=row.get("Crop"),
                )
            obj.value = row.get("CropYield_bu_ac") if row.get("CropYield_bu_ac") is not None else row.get("Value")
            obj.unit = row.get("DataItem") or row.get("unit")
            if "district" in row and pd.notnull(row["district"]):
                obj.district = row["district"]
            if "county_ansi" in row and pd.notnull(row["county_ansi"]):
                obj.county_ansi = str(row["county_ansi"])
            session.add(obj)
        session.commit()
        logger.info("Upserted %d yield rows for %s.", len(df), df.iloc[0]["County"])

def upsert_weather_psa_to_db(df: pd.DataFrame):
    from app.db_models import WeatherPSA

    if df is None or df.empty:
        logger.debug("No weather data to upsert.")
        return

    with Session(engine) as session:
        for _, row in df.iterrows():
            obj = session.exec(
                select(WeatherPSA).where(
                    WeatherPSA.year == int(row["Year"]),
                    WeatherPSA.date == row["Date"],
                    WeatherPSA.county == row["County"],
                    WeatherPSA.state == row["State"],
                )
            ).first()
            if obj is None:
                obj = WeatherPSA(year=int(row["Year"]), date=row["Date"], county=row["County"], state=row["State"])
                obj.source = row.get("Source")
                obj.lat = row.get("Lat")
                obj.lon = row.get("Lon")
                obj.precipitation = row.get("Precipitation")
                obj.longwave_radiation = row.get("Longwave_Radiation")
                obj.shortwave_radiation = row.get("Shortwave_Radiation")
                obj.potential_energy = row.get("Potential_Energy")
                obj.potential_evaporation = row.get("Potential_Evaporation")
                obj.convective_precipitation = row.get("Convective_Precipitation")
                obj.min_air_temperature = row.get("Min_Air_Temperature")
                obj.max_air_temperature = row.get("Max_Air_Temperature")
                obj.avg_air_temperature = row.get("Avg_Air_Temperature")
                obj.min_humidity = row.get("Min_Humidity")
                obj.max_humidity = row.get("Max_Humidity")
                obj.avg_humidity = row.get("Avg_Humidity")
                obj.min_relative_humidity = row.get("Min_Relative_Humidity")
                obj.max_relative_humidity = row.get("Max_Relative_Humidity")
                obj.avg_relative_humidity = row.get("Avg_Relative_Humidity")
                obj.min_pressure = row.get("Min_Pressure")
                obj.max_pressure = row.get("Max_Pressure")
                obj.avg_pressure = row.get("Avg_Pressure")
                obj.min_zonal_wind_speed = row.get("Min_Zonal_Wind_Speed")
                obj.max_zonal_wind_speed = row.get("Max_Zonal_Wind_Speed")
                obj.avg_zonal_wind_speed = row.get("Avg_Zonal_Wind_Speed")
                obj.min_meridional_wind_speed = row.get("Min_Meridional_Wind_Speed")
                obj.max_meridional_wind_speed = row.get("Max_Meridional_Wind_Speed")
                obj.avg_meridional_wind_speed = row.get("Avg_Meridional_Wind_Speed")
                obj.min_wind_speed = row.get("Min_Wind_Speed")
                obj.max_wind_speed = row.get("Max_Wind_Speed")
                obj.avg_wind_speed = row.get("Avg_Wind_Speed")
            session.add(obj)
        session.commit()
        logger.info("Upserted %d weather rows for %s.", len(df), df.iloc[0]["County"])


def main() -> None:
    """
    Bulk ingestion entry point.

    Iterates over every county in each configured state and fetches
    soil (SSURGO), weather (Daymet), and yield (USDA NASS) data.
    Each county is processed independently — a failure for one county
    does not abort the rest.

    Required environment / settings:
        NASS_API_KEY   – USDA NASS QuickStats API key.

    Optional environment variables:
        INGEST_STATES      – Comma-separated state names (default: built-in list).
        INGEST_START_YEAR  – First year to ingest (default: 1980).
        INGEST_END_YEAR    – Last year to ingest (default: 2022).
        DRY_RUN            – Set to any non-empty, non-"0" value to skip DB writes.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    api_key = settings.NASS_API_KEY
    if not api_key:
        logger.error(
            "NASS_API_KEY is not set. Yield ingestion requires a valid USDA NASS API key. "
            "Register for free at https://quickstats.nass.usda.gov/api."
        )
        return

    states_env = os.environ.get("INGEST_STATES", "")
    states = [s.strip() for s in states_env.split(",") if s.strip()] if states_env else DEFAULT_STATES

    start_year = int(os.environ.get("INGEST_START_YEAR", "1980"))
    end_year = int(os.environ.get("INGEST_END_YEAR", "2022"))

    _dry_run_val = os.environ.get("DRY_RUN", "")
    dry_run = bool(_dry_run_val) and _dry_run_val != "0"

    logger.info("Starting bulk ingestion for %d state(s), years %d-%d.", len(states), start_year, end_year)

    for state in states:
        counties = get_counties_for_state(state)
        if not counties:
            logger.warning("No counties found for %s — skipping.", state)
            continue

        total = len(counties)
        for idx, county in enumerate(counties, 1):
            logger.info("[%s %d/%d] Processing %s...", state, idx, total, county)

            if dry_run:
                logger.info("  DRY RUN — skipping fetch for %s, %s.", county, state)
                continue

            try:
                soil_df = fetch_and_transform_soil(county, state)
                upsert_soil_to_db(soil_df)
            except Exception as exc:
                logger.error("Soil ingestion failed for %s, %s: %s", county, state, exc)

            try:
                weather_result = fetch_and_transform_weather(county, state, start_year, end_year)
                weather_df, daily_df = weather_result if isinstance(weather_result, tuple) else (weather_result, None)
                upsert_weather_to_db(weather_df)
                if daily_df is not None and not daily_df.empty:
                    save_daily_weather_to_db(daily_df, state)
            except Exception as exc:
                logger.error("Weather ingestion failed for %s, %s: %s", county, state, exc)

            try:
                yield_df = fetch_and_transform_yield(api_key, county, state, start_year, end_year)
                upsert_yield_to_db(yield_df)
            except Exception as exc:
                logger.error("Yield ingestion failed for %s, %s: %s", county, state, exc)

            try:
                my_df = fetch_and_transform(county, state, start_year, end_year)
                upsert_weather_psa_to_db(my_df) #← add this upsert function in runner.py too
            except Exception as exc:
                logger.error("MyDataSource ingestion failed for %s, %s: %s", county, state, exc)

    logger.info("Bulk ingestion complete.")


if __name__ == "__main__":
    main()
