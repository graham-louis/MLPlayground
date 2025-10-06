import os
def fetch_and_transform_yield_csv_fallback(api_key, county_name, state_name, start_year, end_year, csv_path=None):
    """
    Filler function: Reads local CSV for North Carolina yield data and mimics the API output format.
    Only supports North Carolina data in /data/crop_yield_1980_2022.csv.
    """
    print("[FILLER] Reading local CSV for yield data...")
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), '../../data/crop_yield_1980-2022.csv')
    df = pd.read_csv(csv_path)
    # Filter for county, state, year, and any Data Item that contains 'YIELD'
    # NOTE: include all commodities (do not filter for only CORN)
    mask = (
        (df['State'].str.upper() == state_name.upper()) &
        (df['County'].str.upper() == county_name.upper()) &
        (df['Data Item'].str.contains('YIELD', case=False)) &
        (df['Year'] >= start_year) & (df['Year'] <= end_year)
    )
    filtered = df[mask]
    if filtered.empty:
        print(f"  - No local CSV yield data found for {county_name}, {state_name}, {start_year}-{end_year}.")
        return pd.DataFrame()
    # Reformat to match API output and include district and county_ansi
    out = filtered[['Year', 'Value', 'Commodity', 'Data Item', 'Ag District', 'County ANSI']].rename(columns={
        'Year': 'Year',
        'Value': 'CropYield_bu_ac',
        'Commodity': 'Crop',
        'Data Item': 'DataItem',
        'Ag District': 'district',
        'County ANSI': 'county_ansi'
    }).copy()
    out['CropYield_bu_ac'] = pd.to_numeric(out['CropYield_bu_ac'], errors='coerce')
    out.dropna(subset=['CropYield_bu_ac'], inplace=True)
    out['Year'] = out['Year'].astype(int)
    out['County'] = county_name
    out['State'] = state_name
    # Clean up district and county_ansi (optional: convert county_ansi to string, handle NaN)
    if 'county_ansi' in out.columns:
        out['county_ansi'] = out['county_ansi'].astype(str).replace('nan', None)
    if 'district' in out.columns:
        out['district'] = out['district'].astype(str).replace('nan', None)
    print("[FILLER] Local CSV yield data processing complete. ✅")
    return out

import requests
import pandas as pd

def fetch_and_transform_yield(api_key, county_name, state_name, start_year, end_year):
    """
    Fetches real annual corn yield data from the USDA NASS API and returns a cleaned DataFrame.
    """
    print("Fetching crop yield data from USDA NASS...")
    if api_key == 'YOUR_API_KEY' or not api_key:
        print("  - ERROR: Please provide a valid USDA NASS API key.")
        return pd.DataFrame()
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    params = {
        'key': api_key,
        'source_desc': 'SURVEY',
        'sector_desc': 'CROPS',
        'group_desc': 'FIELD CROPS',
        # do not restrict to a single commodity so we return all commodities
        'statisticcat_desc': 'YIELD',
        'unit_desc': 'BU / ACRE',
        'agg_level_desc': 'COUNTY',
        'state_name': state_name.upper(),
        'county_name': county_name.upper(),
        'year__GE': start_year,
        'year__LE': end_year,
        'format': 'JSON'
    }
    response = requests.get(base_url, params=params)
    print(response.url)
    if response.status_code == 200:
        data = response.json().get('data', [])
        if not data:
            print("  - No yield data found for the specified parameters.")
            return pd.DataFrame()
        yield_df = pd.DataFrame(data)
        # --- Data Cleaning ---
        # Keep commodity information when present
        if 'commodity_desc' in yield_df.columns:
            cols = ['year', 'Value', 'commodity_desc']
            yield_df = yield_df[[c for c in cols if c in yield_df.columns]].rename(columns={
                'year': 'Year',
                'Value': 'CropYield_bu_ac',
                'commodity_desc': 'Crop'
            })
        else:
            yield_df = yield_df[['year', 'Value']].rename(columns={
                'year': 'Year',
                'Value': 'CropYield_bu_ac'
            })
        # remove thousands separators and coerce
        if yield_df['CropYield_bu_ac'].dtype == object:
            yield_df['CropYield_bu_ac'] = yield_df['CropYield_bu_ac'].str.replace(',', '')
        yield_df['CropYield_bu_ac'] = pd.to_numeric(yield_df['CropYield_bu_ac'], errors='coerce')
        yield_df.dropna(inplace=True)
        yield_df['Year'] = yield_df['Year'].astype(int)
        yield_df['County'] = county_name
        yield_df['State'] = state_name
        print("USDA NASS data processing complete. ✅")
        return yield_df
    else:
        print(f"  - Failed to get USDA data. Status: {response.status_code}")
        print(f"  - Response: {response.text}")
        return pd.DataFrame()

# Optional CLI for ingestion
if __name__ == "__main__":
    import argparse
    import os
    from sqlalchemy import create_engine
    parser = argparse.ArgumentParser(description="Yield ingestion runner")
    parser.add_argument('--api_key', required=True)
    parser.add_argument('--county', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--start_year', type=int, required=True)
    parser.add_argument('--end_year', type=int, required=True)
    parser.add_argument('--db', default=os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db"))
    args = parser.parse_args()
    engine = create_engine(args.db)
    yield_df = fetch_and_transform_yield(args.api_key, args.county, args.state, args.start_year, args.end_year)
    from backend.ingest.runner import upsert_yield_to_db
    upsert_yield_to_db(yield_df, engine)
