import streamlit as st
import pandas as pd
import os
import numpy as np
from utils.getYieldData import get_yield_data
from utils.getSoilData import get_soil_data
from utils.getWeatherData import *
import requests



NASS_API_KEY = "77B33341-6DF0-3F4A-ADBE-518926034592"

st.set_page_config(page_title="AutoML")

st.write("# AutoML")

with st.sidebar:
    st.success("Select an option above.")
    st.info("Build automated ML pipeline using Streamlit, Pandas Profiling, and PyCaret.")
    

st.markdown("""
This app allows you to: 
- Upload data
- Create a profile report
- Select features and a target variable
- Compare a suite of Machine Learning classification and regression models.
"""
)

def get_counties_for_state(state_name):
    """Queries the SDM API to get a list of all counties in a given state."""
    print(f"Fetching county list for {state_name}...")
    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    query = f"SELECT areaname FROM sacatalog WHERE areaname LIKE '%, {state_name}'"

    try:
        response = requests.post(sdm_api_url, data={"FORMAT": "JSON", "QUERY": query})
        response.raise_for_status()
        data = response.json()['Table']
        if len(data) < 2: return []

        # Extract just the county name from "County Name, State"
        county_list = [row[0].split(" County,")[0] for row in data[1:]]
        print(f"Found {len(county_list)} counties.")
        return sorted(county_list)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching county list: {e}")
        return []

if st.button("Download data"):

    print("Button Pressed")
    state_name = "North Carolina"
    counties = get_counties_for_state(state_name=state_name)
    start_year = 1980
    end_year = 2022

    st.text(f"Getting data for all counties in {state_name}")

    st.dataframe(counties)

    if os.path.exists("data/soil_data.csv") and os.path.exists("data/annual_weather.csv"):
        st.info("Data found, reading now...")
        soil_data_df = pd.read_csv("data/soil_data.csv", index_col=None)
        annual_weather_df = pd.read_csv("data/annual_weather.csv", index_col=None)
        daily_weather_df = pd.read_csv("data/daily_weather.csv", index_col=None)
    else:
        st.info("Downloading data now...")
        soil_data = []
        annual_weather = []
        daily_weather = []
        for county in counties:
            county_soil_data = get_soil_data(county_name=county, state_name=state_name)
            # add rows 
            soil_data.append(county_soil_data)

            county_annual_weather, county_daily_weather = get_weather_daymet(county_name=county, state_name=state_name, start_year=start_year, end_year=end_year)
            annual_weather.append(county_annual_weather)
            daily_weather.append(county_daily_weather)
        
        soil_data_df = pd.concat(soil_data, ignore_index=True)
        soil_data_df.to_csv("data/soil_data.csv", index=None)

        annual_weather_df = pd.concat(annual_weather, ignore_index=True)
        annual_weather_df.to_csv("data/annual_weather.csv", index=None)
        daily_weather_df = pd.concat(daily_weather, ignore_index=True)
        daily_weather_df.to_csv("data/daily_weather.csv", index=None)

        # st.success("Data download complete!", description="Soil and weather data saved to CSV files.")

    # Conver annual weather county names to upper case to match yield data
    annual_weather_df['County'] = annual_weather_df['County'].str.upper()

    yield_data = pd.read_csv("data/crop_yield_1980-2022.csv", index_col=None)
    # Select Year, County, Commodity, Value
    yield_data = yield_data[['Year', 'County', 'State', 'Commodity', 'Value']]
    # Filter for commodity = CORN
    yield_data = yield_data[(yield_data['Commodity'] == 'SOYBEANS') & (yield_data['Year'] >= start_year) & (yield_data['Year'] <= end_year)]
    yield_data = yield_data.rename(columns={'Value': 'Yield'})
    yield_data = yield_data[['Year', 'County', 'Yield']]
    # Merge yield and weather data on Year and County
    df = pd.merge(yield_data, annual_weather_df, on=['Year', 'County'], how='left')

    st.session_state['df'] = df

    # yield_data = get_yield_data(NASS_API_KEY, county_name=counties[0], state_name=state_name, start_year=start_year, end_year=end_year)
    # yield_data.to_csv("yield_data.csv")

# if os.path.exists("sourcedata.csv"):
#     df = pd.read_csv("sourcedata.csv", index_col=None)
#     if 'df' not in st.session_state:
#         st.session_state['df'] = df
