import streamlit as st

st.set_page_config(page_title="Download Model", page_icon="⬇️")

st.sidebar.header("Download Your Model")

st.title("Download Your Model")

with open("best_model.pkl", 'rb') as f:
        st.download_button("Download the Model", f, "trained_model.pkl")