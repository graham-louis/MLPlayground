import sys
import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.ingest.ssurgo import fetch_and_transform_soil
from backend.ingest.nldas import fetch_and_transform_weather
from backend.ingest.nass import fetch_and_transform_yield_csv_fallback, fetch_and_transform_yield
from backend.config import get_nass_api_key, get_database_url


def upsert_soil_to_db(df, engine):
    """
    Upserts a single-row DataFrame of soil features into the soil table.
    Assumes columns: Soil_pH, Soil_CEC, PercentSand, PercentClay, OM_percent, County
    """
    from db.models import Soil
    if df is None or df.empty:
        print("No soil data to upsert.")
        return
    row = df.iloc[0]
    with Session(engine) as session:
        # Upsert by county and state
        obj = session.query(Soil).filter_by(county=row['County'], state=row['State']).first()
        if obj is None:
            obj = Soil(county=row['County'], state=row['State'])
        obj.ph = row['Soil_pH']
        obj.organic_matter = row['OM_percent']
        obj.sand_pct = row['PercentSand']
        obj.clay_pct = row['PercentClay']
        # silt_pct could be computed if available
        session.add(obj)
        session.commit()
        print(f"Upserted soil data for {row['County']}, {row['State']}")

def upsert_weather_to_db(df, engine):
    """
    Upserts annual weather features into the weather table.
    Assumes columns: Year, TotalPrecip_mm, AvgTemp_C, TotalGDD, County, State
    """
    from db.models import Weather
    if df is None or df.empty:
        print("No weather data to upsert.")
        return
    for _, row in df.iterrows():
        with Session(engine) as session:
            obj = session.query(Weather).filter_by(
                year=row['Year'], county=row['County'], state=row['State']
            ).first()
            if obj is None:
                obj = Weather(year=row['Year'], county=row['County'], state=row['State'])
            obj.avg_temp = row.get('AvgTemp_C')
            obj.precipitation = row.get('TotalPrecip_mm')
            obj.gdd = row.get('TotalGDD')
            obj.vp = row.get('vp')  # Vapor pressure
            obj.srad = row.get('srad')  # Solar radiation
            session.add(obj)
            session.commit()
            print(f"Upserted weather data for {row['County']}, {row['State']}, {row['Year']}")

def upsert_yield_to_db(df, engine):
    """
    Upserts annual yield data into the yield table.
    Assumes columns: Year, CropYield_bu_ac, County, State
    """
    from db.models import Yield
    if df is None or df.empty:
        print("No yield data to upsert.")
        return
    for _, row in df.iterrows():
        with Session(engine) as session:
            obj = session.query(Yield).filter_by(
                year=row['Year'], county=row['County'], state=row['State'], crop=row.get('Crop', None)
            ).first()
            if obj is None:
                obj = Yield(year=row['Year'], county=row['County'], state=row['State'], crop=row.get('Crop', None))
            # db model uses 'value' and 'unit'
            obj.value = row.get('CropYield_bu_ac') if row.get('CropYield_bu_ac') is not None else row.get('Value')
            # DataItem/commodity unit may be present
            obj.unit = row.get('DataItem') or row.get('unit')
            # Set district and county_ansi if present
            if 'district' in row and pd.notnull(row['district']):
                obj.district = row['district']
            if 'county_ansi' in row and pd.notnull(row['county_ansi']):
                obj.county_ansi = str(row['county_ansi'])
            session.add(obj)
            session.commit()
            print(f"Upserted yield data for {row['County']}, {row['State']}, {row['Year']}, crop={obj.crop}")


def main():
    """Default CSV-driven bulk ingestion (no CLI args).

    Reads `/crop_yield_1980_2022.csv` from the repo and for each
    County/State group computes the year range and ingests soil, weather,
    and yield (via NASS API) data into the database.
    """
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    # Get NASS API key from config
    api_key = get_nass_api_key()
    if not api_key:
        print("WARNING: NASS_API_KEY not found in environment variables or .env file.")
        print("         Falling back to CSV fallback for yield data.")
        print("         To use the NASS API, set NASS_API_KEY in your .env file or environment.")
        use_api = False
    else:
        use_api = True

    print("\n--- BULK INGESTION FROM CSV (default) ---")
    csv_path = os.path.join(os.path.dirname(__file__), '../../crop_yield_1980-2022.csv')
    print(f"Reading CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        return

    # Ensure required cols exist
    required = ['County', 'State', 'Year']
    for r in required:
        if r not in df.columns:
            print(f"CSV missing required column: {r}")
            return

    grouped = df.groupby(['County', 'State'])
    for (county, state), group in grouped:
        county = str(county).strip()
        state = str(state).strip()
        years = group['Year'].dropna().astype(int)
        if years.empty:
            continue
        start_y, end_y = int(years.min()), int(years.max())
        print(f"\nProcessing {county}, {state}: {start_y}-{end_y}")
        dry_run = bool(os.environ.get('DRY_RUN', '') and os.environ.get('DRY_RUN') != '0')
        if dry_run:
            print(f"  - DRY RUN: would fetch soil for {county}, {state}")
            print(f"  - DRY RUN: would fetch weather for {county}, {state} years {start_y}-{end_y}")
            if use_api:
                print(f"  - DRY RUN: would fetch yield from NASS API for {county}, {state} years {start_y}-{end_y}")
            else:
                print(f"  - DRY RUN: would ingest yield from local CSV for {county}, {state} years {start_y}-{end_y}")
            continue
        # Soil
        soil_df = fetch_and_transform_soil(county, state)
        upsert_soil_to_db(soil_df, engine)
        # Weather
        weather_df = fetch_and_transform_weather(county, state, start_y, end_y)
        if isinstance(weather_df, tuple):
            weather_df = weather_df[0]
        upsert_weather_to_db(weather_df, engine)
        # Yield (NASS API or CSV fallback)
        if use_api:
            yield_df = fetch_and_transform_yield(api_key, county, state, start_y, end_y)
        else:
            yield_df = fetch_and_transform_yield_csv_fallback(county, state, start_y, end_y)
        upsert_yield_to_db(yield_df, engine)

if __name__ == "__main__":
    main()
