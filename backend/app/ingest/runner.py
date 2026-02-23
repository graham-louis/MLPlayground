import logging
import os
import re

import pandas as pd
import requests
from sqlmodel import Session, select

from app.core.db import engine
from app.ingest.climate_nldas import _validate_name, fetch_and_transform_weather
from app.ingest.crop_nass import fetch_and_transform_yield, fetch_and_transform_yield_csv_fallback
from app.ingest.soil_ssurgo import fetch_and_transform_soil
from app.core.config import settings

logger = logging.getLogger(__name__)


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
    """
    Upserts a single-row DataFrame of soil features into the soil table.
    All work is done in a single session.
    """
    from app.models import Soil

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
    """
    Upserts annual weather rows into the weather table in a single session/transaction.
    """
    from app.models import Weather

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
    """
    Upserts annual yield rows into the yield table in a single session/transaction.
    """
    from app.models import Yield

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


def main() -> None:
    """
    Default CSV-driven bulk ingestion.

    Reads ``crop_yield_1980-2022.csv`` from the repo root and for each
    County/State group ingests soil, weather, and yield data.
    Each county is processed independently — a failure for one county
    does not abort the rest.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    api_key = settings.NASS_API_KEY
    use_api = bool(api_key)
    if not use_api:
        logger.warning("NASS_API_KEY not set — falling back to CSV for yield data.")

    csv_path = os.path.join(os.path.dirname(__file__), "../../../crop_yield_1980-2022.csv")
    logger.info("Reading CSV: %s", csv_path)
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        logger.error("Failed to read CSV: %s", exc)
        return

    required = ["County", "State", "Year"]
    for col in required:
        if col not in df.columns:
            logger.error("CSV missing required column: %s", col)
            return

    _dry_run_val = os.environ.get("DRY_RUN", "")
    dry_run = bool(_dry_run_val) and _dry_run_val != "0"
    grouped = df.groupby(["County", "State"])
    total = len(grouped)
    for idx, ((county, state), group) in enumerate(grouped, 1):
        county = str(county).strip()
        state = str(state).strip()
        years = group["Year"].dropna().astype(int)
        if years.empty:
            continue
        start_y, end_y = int(years.min()), int(years.max())
        logger.info("[%d/%d] Processing %s, %s (%d-%d)...", idx, total, county, state, start_y, end_y)

        if dry_run:
            logger.info("  DRY RUN — skipping fetch for %s, %s.", county, state)
            continue

        # Per-county error isolation: log and continue on any failure
        try:
            soil_df = fetch_and_transform_soil(county, state)
            upsert_soil_to_db(soil_df)
        except Exception as exc:
            logger.error("Soil ingestion failed for %s, %s: %s", county, state, exc)

        try:
            weather_result = fetch_and_transform_weather(county, state, start_y, end_y)
            weather_df = weather_result[0] if isinstance(weather_result, tuple) else weather_result
            upsert_weather_to_db(weather_df)
        except Exception as exc:
            logger.error("Weather ingestion failed for %s, %s: %s", county, state, exc)

        try:
            if use_api:
                yield_df = fetch_and_transform_yield(api_key, county, state, start_y, end_y)
            else:
                yield_df = fetch_and_transform_yield_csv_fallback(county, state, start_y, end_y)
            upsert_yield_to_db(yield_df)
        except Exception as exc:
            logger.error("Yield ingestion failed for %s, %s: %s", county, state, exc)

    logger.info("Bulk ingestion complete.")


if __name__ == "__main__":
    main()
