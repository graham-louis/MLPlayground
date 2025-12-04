import streamlit as st
import pandas as pd
import shap
import lime
import lime.lime_tabular
import matplotlib.pyplot as plt
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.utils.filter_display import display_selected_filters, display_filters_in_sidebar

st.set_page_config(page_title="Explainability", page_icon="🧠")
st.title("Model Explainability: SHAP & LIME")

# Display selected filters
display_selected_filters()

# Display filters in sidebar
display_filters_in_sidebar()

st.markdown("""
**Why Explainability?**

MLPlayground is designed to make crop yield forecasting transparent and trustworthy. Every prediction is accompanied by model-agnostic explanations so users can understand the climatic and soil drivers behind forecasts.

**Key Goals:**
- Explain every prediction using SHAP and LIME
- Visualize feature importances and local explanations
- Provide plain-language interpretation of model results
""")

if 'best_model' not in st.session_state or st.session_state.best_model is None:
	st.warning("Train a model first to see explanations.")
	st.stop()
if 'df' not in st.session_state:
	st.warning("No data available. Please load and merge data first.")
	st.stop()


df = st.session_state.df
model = st.session_state.best_model
target = 'yield'
# Use the actual features used by PyCaret for training
features = st.session_state.get('best_model_features', [col for col in df.columns if col != target])


st.header("Global Feature Importance (SHAP)")
if st.button("Generate SHAP Explanation"):
	try:
		X = df[features].fillna(df[features].mean())
		explainer = shap.Explainer(model.predict, X)
		shap_values = explainer(X)
		fig, ax = plt.subplots(figsize=(8, 4))
		shap.plots.bar(shap_values, show=False)
		st.pyplot(fig)
		st.caption("SHAP summary plot: Features ranked by their overall impact on model output.")
	except Exception as e:
		st.error(f"SHAP explanation failed: {e}")


st.header("Local Explanation (LIME)")

try:
    X = df[features].fillna(df[features].mean())
    lime_explainer = lime.lime_tabular.LimeTabularExplainer(
        X.values,
        feature_names=features,
        class_names=[target],
        mode='regression',
        discretize_continuous=True
    )
    # County selection first, with year count in label
    if 'county' in df.columns and 'year' in df.columns:
        county_year_counts = df.groupby('county')['year'].nunique().to_dict()
        counties = sorted(df['county'].dropna().unique())
        county_labels = [f"{c} ({county_year_counts.get(c, 0)} years)" for c in counties]
        county_label_map = dict(zip(county_labels, counties))
        selected_county_label = st.selectbox("Select a county (years of data)", county_labels)
        selected_county = county_label_map[selected_county_label]
        filtered_df = df[df['county'] == selected_county]
    else:
        filtered_df = df.copy()
        selected_county = None

    # Year selection, filtered by county
    if 'year' in filtered_df.columns:
        years = sorted(filtered_df['year'].dropna().unique())
        selected_year = st.selectbox("Select a year to explain", years)
        filtered_df = filtered_df[filtered_df['year'] == selected_year]
    else:
        selected_year = None

    # Crop selection, filtered by county/year
    if 'crop' in filtered_df.columns:
        crops = sorted(filtered_df['crop'].dropna().unique())
        if len(crops) > 1:
            selected_crop = st.selectbox("Select a crop", crops)
            filtered_df = filtered_df[filtered_df['crop'] == selected_crop]
        else:
            selected_crop = crops[0] if crops else None
    else:
        selected_crop = None

    # Get the first matching row index
    if not filtered_df.empty:
        row_idx = filtered_df.index[0]
        exp = lime_explainer.explain_instance(X.loc[row_idx].values, model.predict, num_features=8)
        st.write(f"**Explanation for county {selected_county if selected_county else ''}, year {selected_year if selected_year else ''}{', crop ' + selected_crop if selected_crop else ''}:**")
        fig2 = exp.as_pyplot_figure()
        st.pyplot(fig2)
        st.caption("LIME local explanation: Feature contributions for a single prediction.")
    else:
        st.warning("No data found for the selected filters.")
except Exception as e:
    st.error(f"LIME explanation failed: {e}")

st.markdown("""
---
**How to interpret these plots:**
- **SHAP summary plot:** Shows which features are most influential across all predictions.
- **LIME local explanation:** Shows how each feature contributed to a specific prediction.

For more details, see the [project README](https://github.com/graham-louis/MLPlayground).
""")

