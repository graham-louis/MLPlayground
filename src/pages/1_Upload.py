import streamlit as st
import pandas as pd

st.set_page_config(page_title="Upload Data", page_icon="⬆️")

st.sidebar.header("Upload Data")

st.title("Upload Your Data for Modeling")

file = st.file_uploader("Upload Your Dataset Here")
if file:
    df = pd.read_csv(file, index_col=None)
    df.to_csv("sourcedata.csv", index=None)
    st.dataframe(df)
    st.session_state['df'] = df # Store in session state for persistence accross pages