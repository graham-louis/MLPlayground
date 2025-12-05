import requests
import streamlit as st
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.utils.db_access import get_yield_data, get_weather_data, get_soil_data

st.set_page_config(page_title="Select Data", page_icon="🔎")
st.title("Select Data for Modeling")

# --- Data Flow Explanation ---
st.markdown("""
**Data Flow:**
1. User selects a crop and year range to use for modeling.
2. On clicking 'Fetch Data', the app queries the database (or APIs in future) for matching records.
3. Results are loaded into `st.session_state['df']` for use by downstream pages (profiling, modeling, etc).
4. The user sees a preview and feedback on the number of records loaded.
""")

    
state_name = "North Carolina"
start_year = 1980
end_year = 2024
crop = st.selectbox("Select crop for analysis", ["SOYBEANS", "CORN", "WHEAT", "COTTON", "PEANUTS"])

start_year, end_year = st.slider("Select a range of years to include in training", 1980, 2024, (1980, 2024))

if st.button("Load data"):

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
    st.dataframe(yield_data.tail())
    st.write("Sample soil data:")
    st.dataframe(soil_data_df.head())
    st.write("Sample weather data:")
    st.dataframe(weather_data_df.head())

    # Merge yield and weather data on Year and County
    if 'year' in yield_data.columns and 'county' in yield_data.columns and \
        'year' in weather_data_df.columns and 'county' in weather_data_df.columns and \
        'county' in soil_data_df.columns:

        # Drop id columns to avoid merge conflicts
        if 'id' in yield_data.columns:
            yield_data = yield_data.drop(columns=['id'])
        if 'id' in weather_data_df.columns:
            weather_data_df = weather_data_df.drop(columns=['id'])
        if 'id' in soil_data_df.columns:
            soil_data_df = soil_data_df.drop(columns=['id'])

            


        merged = pd.merge(yield_data, weather_data_df, on=['year', 'county'], how='left', indicator=True)
        # drop state_y
        if 'state_y' in merged.columns:
            merged = merged.drop(columns=['state_y'])
        # rename state_x to state
        if 'state_x' in merged.columns:
            merged = merged.rename(columns={'state_x': 'state'})

        # 
        missing_weather = merged[merged['_merge'] == 'left_only']
        st.write(f"Rows in yield data with no weather match: {len(missing_weather)}")
        if not missing_weather.empty:
            st.dataframe(missing_weather)

        merged = merged.drop(columns=['_merge'])
        merged = pd.merge(merged, soil_data_df, on=['county'], how='left', indicator=True)
            # drop state_y
        if 'state_y' in merged.columns:
            merged = merged.drop(columns=['state_y'])
        # rename state_x to state
        if 'state_x' in merged.columns:
            merged = merged.rename(columns={'state_x': 'state'})

        missing_soil = merged[merged['_merge'] == 'left_only']
        st.write(f"Rows in yield data with no soil match: {len(missing_soil)}")
        if not missing_soil.empty:
            st.dataframe(missing_soil)
        
        merged = merged.drop(columns=['_merge'])

        # Rename value to Yield
        if 'value' in merged.columns:
            merged = merged.rename(columns={'value': 'yield'})
        
        merged = merged[merged["county"] != "OTHER (COMBINED) COUNTIES"]
        merged = merged[merged["county"] != "OTHER COUNTIES"]
        

        st.write(f"""Counties: {merged["county"].unique().tolist()}""")
        
        
        st.session_state['df'] = merged
        
        # Store the selected filters in session state
        st.session_state['selected_crop'] = crop
        st.session_state['selected_year_range'] = (start_year, end_year)
    else:
        st.warning("Could not merge yield and weather data: missing columns.")

    st.subheader("Merged Data Sample")
    if 'df' in st.session_state:
        st.dataframe(st.session_state['df'].head())



