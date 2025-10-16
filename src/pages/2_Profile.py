import streamlit as st
import pandas as pd
import seaborn as sns
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Profiling capability
from ydata_profiling import ProfileReport
from streamlit_ydata_profiling import st_profile_report
from src.utils.filter_display import display_selected_filters, display_filters_in_sidebar


st.set_page_config(page_title="Profile Data", page_icon="🔎")

st.sidebar.header("Profile Data")

st.title("Auto-Exploratory Data Analysis")

# Display selected filters
display_selected_filters()

# Display filters in sidebar
display_filters_in_sidebar()

# if os.path.exists("sourcedata.csv"):
#     df = pd.read_csv("sourcedata.csv", index_col=None)
#     if 'df' not in st.session_state:
#         st.session_state['df'] = df

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




  
