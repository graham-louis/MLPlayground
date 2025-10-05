# Explainability (SHAP & LIME)

This document describes how MLPlayground generates and stores model explainability artifacts.

## Goals

- Provide both global and local explanations for models trained in the portal.
- Persist explanation artifacts (tables and plots) alongside serialized model files for later inspection.
- Surface explanations in the Streamlit UI so users can understand the drivers of each prediction.

## Tools

- SHAP: preferred for global feature importance and consistent local explanations for tree-based models.
- LIME: used for quick local explanations on individual predictions; useful for human-readable local insights.

## Workflow

1. Train model via PyCaret on the selected DataFrame.
2. After selecting the final model, compute SHAP values (e.g., using TreeExplainer for tree-based models).
3. Save SHAP summary (feature importance) as a CSV and a plot (png) alongside the serialized model.
4. For selected predictions, compute LIME explanations and store the textual explanation or small HTML snippet.
5. The Streamlit Model page reads these artifacts and renders them next to model performance metrics.

## Storage

- Models saved in the repository root (e.g., `best_model_classification.pkl`).
- SHAP artifacts stored under `artifacts/shap/` with subfolders per model and timestamp.
- LIME artifacts stored under `artifacts/lime/` similarly organized.

## Example (pseudo-code)

```python
import shap
# after training `model` and having `X_train`
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_train)
# save summary
shap.summary_plot(shap_values, X_train, show=False)
plt.savefig('artifacts/shap/model_x_summary.png')
# save table
pd.DataFrame(shap_values).to_csv('artifacts/shap/model_x_values.csv')
```

## Streamlit integration

- On the Model page, provide UI to toggle between global SHAP summary and per-sample explanations.
- For local predictions, render the LIME output or a small SHAP force plot embedded via HTML.

---

Expand this doc with code snippets and exact file paths when the model saving conventions are finalized.
