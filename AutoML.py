import streamlit as st
import pandas as pd
import os
import numpy as np

# Profiling capability
from ydata_profiling import ProfileReport
from streamlit_ydata_profiling import st_profile_report

# ML stuff
import pycaret.classification as pcc
import pycaret.regression as pcr

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

if os.path.exists("sourcedata.csv"):
    df = pd.read_csv("sourcedata.csv", index_col=None)
    if 'df' not in st.session_state:
        st.session_state['df'] = df
