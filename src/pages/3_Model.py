import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# ML stuff
import pycaret.classification as pcc
import pycaret.regression as pcr
from src.utils.filter_display import display_selected_filters, display_filters_in_sidebar

st.set_page_config(page_title="Create Models", page_icon="📈")

st.sidebar.header("Create Models")

st.title("Machine Learning")

# Display selected filters
display_selected_filters()

# Display filters in sidebar
display_filters_in_sidebar()

# Load session state variables if they exist

if 'best_model' not in st.session_state:
    st.session_state.best_model = None
if 'model_problem_type' not in st.session_state:
    st.session_state.model_problem_type = None

df = st.session_state.df

target = 'yield'
problem = 'Regression'  # default

# Default important features (edit as needed)
default_features = [
    'avg_temp', 'precipitation', 'gdd', 'sand_pct', 'clay_pct', 'ph', 'organic_matter'
]
available_features = [col for col in default_features if col in df.columns and col != target]

# This is a placeholder for feature selection report
# --- MRMR Feature Selection ---
from sklearn.feature_selection import mutual_info_regression
import numpy as np
if 'mrmr_report' not in st.session_state:
    mrmr_candidates = [col for col in df.columns if col != target and pd.api.types.is_numeric_dtype(df[col]) and col != 'year']
    if mrmr_candidates:
        X = df[mrmr_candidates].fillna(df[mrmr_candidates].mean())
        y = df[target]
        mi = mutual_info_regression(X, y, random_state=0)
        mrmr_df = pd.DataFrame({'feature': mrmr_candidates, 'relevance': mi})
        mrmr_df = mrmr_df.sort_values('relevance', ascending=False)
        st.session_state['mrmr_report'] = mrmr_df


# --- MRMR Feature Selection Report ---
st.subheader("Feature Selection: MRMR Report")
if 'mrmr_report' in st.session_state:
    st.dataframe(st.session_state['mrmr_report'])
    st.caption("MRMR = Minimum Redundancy Maximum Relevance. Top features are most relevant to the target and least redundant with each other.")
else:
    st.info("MRMR report not available. Run feature selection in the profiling step or upload a report to st.session_state['mrmr_report'].")

# Model Configuration
with st.container(border=True):
    st.subheader("Model Configuration")
    st.markdown("Select which features to use for training. MRMR top features are recommended.")
    col1, col2 = st.columns(2)
    with col1:
        if 'mrmr_report' in st.session_state:
            mrmr_features = st.session_state['mrmr_report']['feature'].tolist()
            features = st.multiselect("Features", df.columns[df.columns != target], default=mrmr_features[:5])
        else:
            features = st.multiselect("Features", df.columns[df.columns != target])
    with col2:
        st.write("Selected features:")
        st.write(features)
    
    training_scope = st.radio(
        "Select Training Data Scope",
        ("Train model on entire dataset", "Train model on specific ag district"),
        key="training_scope"
    )

    if training_scope == "Train model on specific ag district":
        unique_districts = sorted(df['district'].unique().tolist())
        selected_districts = st.multiselect("Select Agricultural Districts", options=unique_districts)

        # Filter the dataframe based on selection
        if selected_districts:
            df_train = df[df['district'].isin(selected_districts)]
        else:
            # If no district is selected yet, prevent the app from crashing
            st.warning("Please select at least one district to proceed.")
            st.stop()
    else:
        df_train = df.copy()


# Model Training
if st.button("Train Model"):
    with st.spinner("Training Models..."):
        train_df = df_train[features + [target]] if features else df_train
        pcr.setup(train_df, target=target)
        # Store the actual features used by PyCaret after preprocessing
        used_features = pcr.get_config('X_train').columns.tolist()
        st.session_state['best_model_features'] = used_features
        setup_df = pcr.pull()
        st.info("ML Experiment Settings (Regression)")
        st.dataframe(setup_df)
        best_model = pcr.compare_models()
        compare_df = pcr.pull()
        st.info("Comparison results (Regression)")
        st.dataframe(compare_df)
        pcr.save_model(best_model, 'best_model_regression')
        pcr.plot_model(best_model, plot='learning', display_format='streamlit')
    st.session_state.best_model = best_model
    st.success("Model training complete!")


# Model Evaluation

if st.session_state.best_model:
    with st.container(border=True):
        st.subheader("Evaluate Best Model")

        st.write("The best performing model is:")
        st.code(str(st.session_state.best_model))

        # Define plot lists based on problem type
        plot_options = [
            'residuals', 'error', 'cooks', 'learning', 'vc', 
            'manifold', 'feature', 'prediction_error'
        ]
        default_plot = 'residuals'
        
        # Create a dropdown to select the plot
        plot_choice = st.selectbox(
            "Choose an evaluation plot:", 
            options=plot_options,
            index=plot_options.index(default_plot)
        )
        
        # Display the selected plot
        st.write(f"Displaying '{plot_choice.replace('_', ' ').title()}' Plot:")
            
        pcr.plot_model(st.session_state.best_model, plot=plot_choice, display_format='streamlit')
            