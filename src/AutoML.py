import streamlit as st
import pandas as pd
import os
import numpy as np
from utils.db_access import get_yield_data, get_soil_data, get_weather_data
import requests

st.set_page_config(page_title="About")

st.write("# MLPlayground: Interactive Crop Yield AutoML Platform")

with st.sidebar:
    st.success("Welcome to MLPlayground!")
    st.info("An interactive, explainable AutoML platform for crop yield forecasting.")
    st.markdown("""
    **Quick Links:**
    - [Project README](https://github.com/graham-louis/MLPlayground)
    - [Docs](#)
    """)

st.markdown("""
**MLPlayground** is a web-based AutoML platform designed for on-demand, localized crop yield forecasting with a focus on explainability and data integration.

---
### **Project Goals**
- **Simple, interactive forecasting:** Select a crop and region to trigger an automated pipeline that trains a custom model in real-time.
- **Integrated data sources:** Combines historical yield (USDA NASS), climate (NASA NLDAS), and soil (SSURGO) data for richer features.
- **Automated agronomic features:** Computes Growing Degree Days (GDD), seasonal aggregates, and more.
- **Explainability first:** Every prediction is accompanied by SHAP/LIME explanations so users can understand the drivers behind forecasts.
- **Regional modeling:** Supports region-specific models (e.g., Piedmont vs Coastal Plains) to capture local climate-crop relationships.

---
### **How It Works**
1. **Data Selection:** Choose a state, county, crop, and year range. Data is loaded from public APIs (no upload required).
2. **Data Enrichment:** The platform fetches and merges yield, weather, and soil data for your region.
3. **Profiling & Diagnostics:** View summary statistics, missing data diagnostics, and feature distributions.
4. **Modeling:** Select a modeling task (regression/classification), choose a model, and train with one click.
5. **Explainability:** Visualize feature importances and local explanations (SHAP/LIME) for each prediction.
6. **Download & Share:** Export trained models, data profiles, and explanations for further analysis.

---
### **Architecture**
- **Frontend:** Streamlit app (this UI)
- **Backend:** FastAPI service for data access and orchestration
- **Database:** PostgreSQL (via SQLAlchemy ORM and Alembic migrations)
- **Data Sources:** USDA NASS, NASA NLDAS, SSURGO

---
### **Intended Audience**
- Agronomists and extension agents seeking transparent, on-demand forecasts
- Data scientists exploring feature engineering and explainability in agriculture
- Developers building modular, production-ready AutoML pipelines

---
### **Get Started**
1. Use the sidebar to select a region and crop.
2. Step through the workflow: Data → Profile → Model → Explain → Download.
3. See the README for troubleshooting and advanced usage.
""")
