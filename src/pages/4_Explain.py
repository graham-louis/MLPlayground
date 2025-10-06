import streamlit as st
import pandas as pd
import shap
import lime
import lime.lime_tabular
import matplotlib.pyplot as plt

st.set_page_config(page_title="Explainability", page_icon="🧠")
st.title("Model Explainability: SHAP & LIME")

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
	idx = st.number_input("Select a row to explain (0 = first row)", min_value=0, max_value=len(df)-1, value=0)
	exp = lime_explainer.explain_instance(X.iloc[idx].values, model.predict, num_features=8)
	st.write(f"**Explanation for row {idx}:**")
	fig2 = exp.as_pyplot_figure()
	st.pyplot(fig2)
	st.caption("LIME local explanation: Feature contributions for a single prediction.")
except Exception as e:
	st.error(f"LIME explanation failed: {e}")

st.markdown("""
---
**How to interpret these plots:**
- **SHAP summary plot:** Shows which features are most influential across all predictions.
- **LIME local explanation:** Shows how each feature contributed to a specific prediction.

For more details, see the [project README](https://github.com/graham-louis/MLPlayground).
""")

