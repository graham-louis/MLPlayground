import requests
import pandas as pd


def get_yield_data(api_key, county_name, state_name, start_year, end_year):
    """
    Fetches real annual corn yield data from the USDA NASS API.
    """
    print("Fetching crop yield data from USDA NASS...")
    if api_key == 'YOUR_API_KEY' or not api_key:
        print("  - ERROR: Please provide a valid USDA NASS API key.")
        return pd.DataFrame()  # Return empty dataframe if no key

    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    params = {
        'key': api_key,
        'source_desc': 'SURVEY',
        'sector_desc': 'CROPS',
        'group_desc': 'FIELD CROPS',
        'commodity_desc': 'CORN',
        'statisticcat_desc': 'YIELD',
        'unit_desc': 'BU / ACRE',
        'agg_level_desc': 'COUNTY',
        'state_name': state_name.upper(),
        'county_name': county_name.upper(),
        'year__GE': start_year,
        'year__LE': end_year,  # LE = Less than or Equal to
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
        # Select and rename columns for consistency
        yield_df = yield_df[['year', 'Value']].rename(columns={
            'year': 'Year',
            'Value': 'CropYield_bu_ac'
        })

        # The 'Value' column is text, convert to numeric and handle non-disclosed '(D)' values
        yield_df['CropYield_bu_ac'] = pd.to_numeric(yield_df['CropYield_bu_ac'].str.replace(',', ''), errors='coerce')
        yield_df.dropna(inplace=True)  # Remove rows with missing yield data
        yield_df['Year'] = yield_df['Year'].astype(int)

        print("USDA NASS data processing complete. ✅")
        return yield_df
    else:
        print(f"  - Failed to get USDA data. Status: {response.status_code}")
        print(f"  - Response: {response.text}")
        return pd.DataFrame()