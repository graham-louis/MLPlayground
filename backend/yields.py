from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session
from db.models import Yield
from backend.ingest.runner import upsert_yield_to_db
from backend.ingest.crop_nass import fetch_and_transform_yield, fetch_and_transform_yield_csv_fallback
from backend.config import get_nass_api_key
from backend.ingest.runner import get_counties_for_state
from backend.orchestrator import ensure_data_for
import os
import logging
logger = logging.getLogger("uvicorn")

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db")
engine = create_engine(DATABASE_URL)

def get_contiguous_ranges(years):
    """
    Convert a sorted list of years into contiguous ranges.
    Returns a list of (start, end) tuples.
    Example: [1990, 1991, 1992, 2021, 2022] -> [(1990, 1992), (2021, 2022)]
    """
    if not years:
        return []
    
    ranges = []
    range_start = years[0]
    range_end = years[0]
    
    for i in range(1, len(years)):
        if years[i] == range_end + 1:
            # Contiguous, extend the range
            range_end = years[i]
        else:
            # Gap found, save current range and start a new one
            ranges.append((range_start, range_end))
            range_start = years[i]
            range_end = years[i]
    
    # Add the last range
    ranges.append((range_start, range_end))
    return ranges

def check_and_fetch_missing_years(state: Optional[str], crop: Optional[str], 
                                   start_year: Optional[int], end_year: Optional[int]):
    """
    Check for missing yield data in the requested year range and fetch/upsert missing data.
    """
    logger.info(f"Checking for missing yield data for state={state}, crop={crop}, years={start_year}-{end_year}")

    # if not start_year or not end_year:
    #     return  # Can't check for missing years without a range

    # Get NASS API key
    api_key = get_nass_api_key()
    use_api = bool(api_key)
    
    with Session(engine) as session:
        # Get all unique (county, state, crop) combinations that match the filters
        query = select(Yield.county, Yield.state, Yield.crop).distinct()
        if state:
            query = query.where(Yield.state == state)
        if crop:
            query = query.where(Yield.crop == crop)
        
        combinations = session.execute(query).all()
        
        # No data from specified state exists, fetch all
        if not combinations:
            counties = get_counties_for_state(state)
            for county in counties:
                yield_df = fetch_and_transform_yield(
                                api_key, county, state, start_year=start_year, end_year=end_year
                            )
                upsert_yield_to_db(yield_df, engine)
            return
        
        
        
        # For each combination, check which years are missing
        for county, state_name, crop_name in combinations:
            # Get existing years for this combination
            year_query = select(Yield.year).where(
                and_(
                    Yield.county == county,
                    Yield.state == state_name,
                    Yield.crop == crop_name,
                    Yield.year >= start_year,
                    Yield.year <= end_year
                )
            )
            existing_years = set(session.execute(year_query).scalars().all())
            
            # Determine missing years
            all_years = set(range(start_year, end_year + 1))
            missing_years = sorted(all_years - existing_years)
            
            if missing_years:
                # Get contiguous ranges of missing years
                missing_ranges = get_contiguous_ranges(missing_years)
                
                # Fetch each contiguous range separately
                for fetch_start, fetch_end in missing_ranges:
                    try:
                        if use_api:
                            yield_df = fetch_and_transform_yield(
                                api_key, county, state_name, fetch_start, fetch_end
                            )
                        else:
                            yield_df = fetch_and_transform_yield_csv_fallback(
                                county, state_name, fetch_start, fetch_end
                            )
                        
                        # Filter to only the missing years in this range and matching crop if specified
                        if not yield_df.empty:
                            # Filter to only missing years in this specific range
                            range_missing_years = set(range(fetch_start, fetch_end + 1))
                            yield_df = yield_df[yield_df['Year'].isin(range_missing_years)]
                            # Filter by crop if we have a crop filter
                            if crop and 'Crop' in yield_df.columns:
                                yield_df = yield_df[yield_df['Crop'] == crop_name]
                            
                            if not yield_df.empty:
                                upsert_yield_to_db(yield_df, engine)
                    except Exception as e:
                        # Log error but continue processing other ranges
                        print(f"Error fetching yield data for {county}, {state_name}, {crop_name}, years {fetch_start}-{fetch_end}: {e}")

@router.get("/yields/")
def get_yields(
    state: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None)
):
    # Check for missing data and fetch if needed
    logger.info("Received yield data request")
    
    # check_and_fetch_missing_years(state, crop, start_year, end_year)
    ensure_data_for(state, start_year, end_year, engine)
    
    with Session(engine) as session:
        query = select(Yield)
        if state:
            query = query.where(Yield.state == state)
        if crop:
            query = query.where(Yield.crop == crop)
        
        if start_year:
            query = query.where(Yield.year >= start_year)
        if end_year:
            query = query.where(Yield.year <= end_year)


        results = session.execute(query).scalars().all()
        # Convert ORM objects to dicts
        return [
            {
                "id": y.id,
                "year": y.year,
                "state": y.state,
                "district": y.district,
                "county": y.county,
                "county_ansi": y.county_ansi,
                "crop": y.crop,
                "value": y.value,
                "unit": y.unit
            }
            for y in results
        ]
