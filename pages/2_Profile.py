import streamlit as st
import pandas as pd
import seaborn as sns
import os

# Profiling capability
from ydata_profiling import ProfileReport
from streamlit_ydata_profiling import st_profile_report


st.set_page_config(page_title="Profile Data", page_icon="🔎")

st.sidebar.header("Profile Data")

st.title("Auto-Exploratory Data Analysis")

if os.path.exists("sourcedata.csv"):
    df = pd.read_csv("sourcedata.csv", index_col=None)
    if 'df' not in st.session_state:
        st.session_state['df'] = df

df = st.session_state.df

profile_report = ProfileReport(df, title="Profiling Report", 
                               correlations={"auto": {"calculate": True},
                                              "pearson": {"calculate": True},
                                              "spearman": {"calculate": True},
                                            "kendall": {"calculate": True},
                                            "phi_k": {"calculate": True},
                                            "cramers": {"calculate": True}})

profile_tab, chart_tab, clean_tab = st.tabs(["Profile", "Chart", "Clean"])

with profile_tab:
    st_profile_report(profile_report)

with chart_tab:
    pass
    #st.pyplot(sns.heatmap(df.corr(), annot=True, fmt='.2f', cmap='Pastel2', linewidths=2))




  
