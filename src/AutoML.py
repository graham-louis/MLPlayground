import streamlit as st
import pandas as pd
import os
import numpy as np
from utils.db_access import get_yield_data, get_soil_data, get_weather_data
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

crop = st.selectbox("Select crop for analysis", ["SOYBEANS", "CORN", "WHEAT", "COTTON", "PEANUTS"])

if st.button("Download data"):
    print("Button Pressed")
    state_name = "North Carolina"
    start_year = 1980
    end_year = 2022
    

    st.text(f"Getting data for {crop} in {state_name} ({start_year}-{end_year})")

    # Fetch from backend API
    yield_data = get_yield_data(state=state_name, crop=crop)
    soil_data_df = get_soil_data(state=state_name)
    weather_data_df = get_weather_data(state=state_name)

    # Data integrity/diagnostics section
    st.subheader("Data Diagnostics & Integrity Checks")
    st.write(f"Yield rows: {len(yield_data)}")
    st.write(f"Soil rows: {len(soil_data_df)}")
    st.write(f"Weather rows: {len(weather_data_df)}")
    st.write("Sample yield data:")
    st.dataframe(yield_data.head())
    st.write("Sample soil data:")
    st.dataframe(soil_data_df.head())
    st.write("Sample weather data:")
    st.dataframe(weather_data_df.head())

    # Merge yield and weather data on Year and County
    if 'year' in yield_data.columns and 'county' in yield_data.columns and 'year' in weather_data_df.columns and 'county' in weather_data_df.columns:
        merged = pd.merge(yield_data, weather_data_df, on=['year', 'county'], how='left', indicator=True)
        missing_weather = merged[merged['_merge'] == 'left_only']
        st.write(f"Rows in yield data with no weather match: {len(missing_weather)}")
        if not missing_weather.empty:
            st.dataframe(missing_weather.head())
        st.session_state['df'] = merged
    else:
        st.warning("Could not merge yield and weather data: missing columns.")

    st.subheader("Merged Data Sample")
    if 'df' in st.session_state:
        st.dataframe(st.session_state['df'].head())

# if os.path.exists("sourcedata.csv"):
#     df = pd.read_csv("sourcedata.csv", index_col=None)
#     if 'df' not in st.session_state:
#         st.session_state['df'] = df
