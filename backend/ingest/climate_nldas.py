
import requests
import pandas as pd
import daymetpy

def psa_fetch_and_transform_weather(county_name, state_name, start_year, end_year):
    """
    Fetches and processes daily weather data for a location over a range of years,
    aggregating it into an annual feature set. Returns (annual_df, daily_df).
    """
    print(f"Fetching weather data from {start_year} to {end_year} for {county_name}, {state_name}...")
    psa_weather_url = "https://weather.covercrop-data.org/daily"
    all_years_weather = []
    all_daily_weather = []
    for year in range(start_year, end_year + 1):
        print(f"{year}...")
        params = {
            "location": f"{county_name} {state_name}",
            "start": f"{year}-01-01",
            "end": f"{year}-12-31",
            "output": "csv",
            "gddbase": "10"
        }
        response = requests.get(psa_weather_url, params=params)
        if response.status_code == 200:
            import io
            csv_data = pd.read_csv(io.StringIO(response.text))
            csv_data['Year'] = year
            if county_name is not None:
                csv_data['County'] = county_name
            all_daily_weather.append(csv_data)
            # --- Feature Engineering ---
            csv_data['date'] = pd.to_datetime(csv_data['date'])
            growing_season = csv_data[csv_data['date'].dt.month.between(5, 9)]
            t_avg = (growing_season['max_air_temperature'] + growing_season['min_air_temperature']) / 2
            gdd = (t_avg - 10).clip(lower=0)
            annual_features = {
                'Year': year,
                'TotalPrecip_mm': growing_season['precipitation'].sum(),
                'AvgTemp_C': growing_season['avg_air_temperature'].mean(),
                'TotalGDD': gdd.sum(),
                'County': county_name,
                'State': state_name
            }
            all_years_weather.append(annual_features)
        else:
            print(f"  - Failed to get weather for {year}. Status: {response.status_code}")
    print("Weather data processing complete. ✅")
    annual_df = pd.DataFrame(all_years_weather)
    if all_daily_weather:
        daily_df = pd.concat(all_daily_weather, ignore_index=True)
    else:
        daily_df = pd.DataFrame()
    if start_year == end_year:
        return annual_df
    return annual_df, daily_df

# Optional CLI for ingestion
if __name__ == "__main__":
    import argparse
    import os
    from sqlalchemy import create_engine
    parser = argparse.ArgumentParser(description="Weather ingestion runner")
    parser.add_argument('--county', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--start_year', type=int, required=True)
    parser.add_argument('--end_year', type=int, required=True)
    parser.add_argument('--db', default=os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db"))
    args = parser.parse_args()
    engine = create_engine(args.db)
    annual_df = fetch_and_transform_weather(args.county, args.state, args.start_year, args.end_year)
    if isinstance(annual_df, tuple):
        annual_df = annual_df[0]
    from backend.ingest.runner import upsert_weather_to_db
    upsert_weather_to_db(annual_df, engine)


def get_county_bbox(county_name, state_name):
    """
    Queries the USDA SDM API to get the bounding box for a specific county.
    
    Returns:
        A tuple of (min_lon, min_lat, max_lon, max_lat) or None if not found.
    """
    print(f"Fetching bounding box for {county_name}, {state_name}...")
    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    
    # SQL query to select the bounding box columns from the survey area catalog
    query = f"""
    SELECT mbrminx, mbrminy, mbrmaxx, mbrmaxy
    FROM sacatalog
    WHERE areaname = '{county_name} County, {state_name}'
    """
    
    try:
        response = requests.post(sdm_api_url, data={"FORMAT": "JSON", "QUERY": query})
        response.raise_for_status()
        if 'Table' not in response.json():
            print(f"  - Bounding box not found for {county_name}.")
            return None
        data = response.json()['Table']

        
        if len(data) < 1:
            print(f"  - Bounding box not found for {county_name}.")
            return None
        
        # The result is a list of lists, data is in the second list
        coords = data[0]
        # Convert string results to floats
        bbox = tuple(float(c) for c in coords)
        
        return bbox # (min_lon, min_lat, max_lon, max_lat)

    except requests.exceptions.RequestException as e:
        print(f"  - Error fetching bounding box: {e}")
        return None

def get_county_center_coord(county_name, state_name):
    """
    Gets the center latitude and longitude for a specific county.

    Returns:
        A dictionary {'lat': latitude, 'lon': longitude} or None if not found.
    """
    # First, get the bounding box using the existing function
    bbox = get_county_bbox(county_name, state_name)
    
    if bbox:
        # Unpack the bounding box coordinates
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Calculate the center point
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        print(f"Calculated center for {county_name}: (Lat: {center_lat:.4f}, Lon: {center_lon:.4f})")
        
        return {'lat': center_lat, 'lon': center_lon}
    else:
        # If the bounding box couldn't be found, return None
        return None


def fetch_and_transform_weather(county_name, state_name, start_year, end_year):
    lon_lat = get_county_center_coord(county_name, state_name)
    if lon_lat is None:
        print(f"  - Cannot fetch Daymet data without coordinates for {county_name}.")
        return None, None
    lon, lat = lon_lat['lon'], lon_lat['lat']
    
    print(f"Fetching Daymet weather data for {county_name}, {state_name} from {start_year} to {end_year}...")
    
    all_years_weather = []

    try:
        all_daily_weather = daymetpy.daymet_timeseries(lon=lon, lat=lat, start_year=start_year, end_year=end_year)
    except Exception as e:
        print(f"  - Error fetching Daymet data: {e}")
        return None, None
    
    # name first column and convert to datetime
    all_daily_weather.rename(columns={'year': 'Year', 'yday': 'DayOfYear'}, inplace=True)
    all_daily_weather['date'] = pd.to_datetime(all_daily_weather[['Year', 'DayOfYear']].astype(str).agg('-'.join, axis=1), format='%Y-%j')

    if all_daily_weather is None or all_daily_weather.empty:
        print(f"  - No Daymet data found for {county_name}.")
        return None, None
    
    # extract year from date
    all_daily_weather['Year'] = all_daily_weather['date'].dt.year
    all_daily_weather['County'] = county_name

    for year in range(start_year, end_year + 1):
        yearly_data = all_daily_weather[all_daily_weather['Year'] == year]
        if yearly_data.empty:
            print(f"  - No Daymet data for {county_name} in {year}.")
            continue
        
        # --- Feature Engineering ---
        growing_season = yearly_data[yearly_data['date'].dt.month.between(5, 9)]
        t_avg = (growing_season['tmax'] + growing_season['tmin']) / 2
        gdd = (t_avg - 10).clip(lower=0)  # GDD can't be negative
        annual_features = {
            'Year': year,
            'TotalPrecip_mm': growing_season['prcp'].sum(),
            'AvgTemp_C': t_avg.mean()   ,
            'TotalGDD': gdd.sum(),
            'County': county_name,
            'State': state_name,
            'vp': growing_season['vp'].mean(),  # Vapor pressure
            'srad': growing_season['srad'].mean()  # Solar radiation
            
        }
        all_years_weather.append(annual_features)
    print("Daymet weather data processing complete. ✅")
    annual_df = pd.DataFrame(all_years_weather)
    return annual_df, all_daily_weather