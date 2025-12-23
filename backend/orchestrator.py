from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pandas as pd
from backend.checks import yield_exists, weather_exists, soil_exists
from backend.ingest.runner import get_counties_for_state
from backend.ingest.crop_nass import fetch_and_transform_yield
from backend.ingest.climate_nldas import fetch_and_transform_weather
from backend.ingest.soil_ssurgo import fetch_and_transform_soil
from backend.config import get_nass_api_key
from backend.ingest.runner import upsert_yield_to_db, upsert_weather_to_db, upsert_soil_to_db
import logging
logger = logging.getLogger("uvicorn")



def ensure_data_for(state, start_year, end_year, engine):
    results = []
    api_key = get_nass_api_key()
    with Session(engine) as session:
        counties = get_counties_for_state(state)
        for county in counties:
            # If county name contains " AREA ", skip it
            if county.count(" AREA") > 0:
                continue
            if not soil_exists(session, county, state):
                logger.info(f"Fetching soil data for {county}, {state}")
                # upper case county
                county = county.upper()
                df = fetch_and_transform_soil(county, state)
                upsert_soil_to_db(df, engine)
                results.append(f"soil:{county}")
            if not yield_exists(session, county, state, start_year, end_year):
                ydf = fetch_and_transform_yield(api_key, county, state, start_year, end_year)
                upsert_yield_to_db(ydf, engine)
                results.append(f"yield:{county}:{start_year}-{end_year}")
            if not weather_exists(session, county, state, start_year, end_year):
                logger.info(f"Fetching weather data for {county}, {state} ({start_year}-{end_year})")
                wdf = fetch_and_transform_weather(county, state, start_year, end_year)
                # if error ""  - Error fetching Daymet data: " skip
                if wdf == "":
                    continue
                # if tuple, take first element
                wdf = wdf[0] if isinstance(wdf, tuple) else wdf
                upsert_weather_to_db(wdf, engine)
                results.append(f"weather:{county}:{start_year}-{end_year}")
    return results