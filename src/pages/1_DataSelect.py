import requests
import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.utils.db_access import get_yield_data, get_weather_data, get_soil_data

st.set_page_config(page_title="Select Data", page_icon="🔎")
st.title("Select Data for Modeling")

# --- User-friendly data selection UI ---
st.sidebar.header("Data Selection")

state = st.sidebar.selectbox("State", ["NC", "SC", "GA", "All"], index=0)
crop = st.sidebar.selectbox("Crop", ["CORN", "SOYBEANS", "WHEAT", "All"], index=0)
year = st.sidebar.selectbox("Year", [2022, 2023, 2024, 2025, "All"], index=3)

if st.button("Fetch Data"):
    with st.spinner("Retrieving data from all endpoints..."):
        # --- Yields ---
        df = get_yield_data(state=None if state=="All" else state,
                            crop=None if crop=="All" else crop,
                            year=None if year=="All" else year)
        if df is not None and len(df) > 0:
            st.session_state['df'] = df
            st.success(f"Yields: Loaded {len(df)} records.")
            st.dataframe(df)
        else:
            st.warning("Yields: No data found for the selected criteria.")

        # --- Weather ---
        wdf = get_weather_data(state=None if state=="All" else state,
                              year=None if year=="All" else year)
        if wdf is not None and len(wdf) > 0:
            st.success(f"Weather: Loaded {len(wdf)} records.")
            st.dataframe(wdf)
        else:
            st.warning("Weather: No data found for the selected criteria.")

        # --- Soil ---
        sdf = get_soil_data(state=None if state=="All" else state)
        if sdf is not None and len(sdf) > 0:
            st.success(f"Soil: Loaded {len(sdf)} records.")
            st.dataframe(sdf)
        else:
            st.warning("Soil: No data found for the selected criteria.")

# --- Data Flow Explanation ---
st.markdown("""
**Data Flow:**
1. User selects a state, crop, and year (or 'All') in the sidebar.
2. On clicking 'Fetch Data', the app queries the database (or APIs in future) for matching records.
3. Results are loaded into `st.session_state['df']` for use by downstream pages (profiling, modeling, etc).
4. The user sees a preview and feedback on the number of records loaded.
""")

