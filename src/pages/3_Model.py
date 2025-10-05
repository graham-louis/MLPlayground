import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

# ML stuff
import pycaret.classification as pcc
import pycaret.regression as pcr

st.set_page_config(page_title="Create Models", page_icon="📈")

st.sidebar.header("Create Models")

st.title("Machine Learning")

# Load session state variables if they exist

if 'best_model' not in st.session_state:
    st.session_state.best_model = None
if 'model_problem_type' not in st.session_state:
    st.session_state.model_problem_type = None

df = st.session_state.df


# Model Configuration

with st.container(border=True):
    st.subheader("Model Configuration")

    col1, col2 = st.columns(2)

    with col1:
        target = st.selectbox("Select your target", df.columns)
        features = st.multiselect("Features", df.columns[df.columns != target])

    with col2:
        problem = st.radio("Problem Type", ["Classification", "Regression"])


# Model Training

if df[target].hasnans:
    st.warning(f"Target column {target} contains missing values. Rows with missing values will be dropped.")
    df = df.dropna(subset=[target])

if st.button("Train Model"):
    st.session_state.model_problem_type = problem

    with st.spinner("Training Models..."):
        if problem == "Classification":
            pcc.setup(df, target=target)
            setup_df = pcc.pull()
            st.info("ML Experiment Settings (Classification)")
            st.dataframe(setup_df)

            best_model = pcc.compare_models()
            compare_df = pcc.pull()
            st.info("Comparison results (Classification)")
            st.dataframe(compare_df)

            pcc.save_model(best_model, 'best_model_classification')
            pcc.plot_model(best_model, plot='confusion_matrix', display_format='streamlit')

        else:
            pcr.setup(df, target=target)
            setup_df = pcr.pull()
            st.info("ML Experiment Settings (Regression)")
            st.dataframe(setup_df)

            best_model = pcr.compare_models()
            compare_df = pcr.pull()
            st.info("Comparison results (Regression)")
            st.dataframe(compare_df)

            pcr.save_model(best_model, 'best_model_regression')
            # show a regression-appropriate plot
            # pcr.plot_model(best_model, plot='residuals', display_format='streamlit')
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
        if st.session_state.model_problem_type == "Classification":
            plot_options = [
                'auc', 'confusion_matrix', 'pr', 'class_report', 
                'boundary', 'feature', 'learning', 'calibration', 
                'dimension', 'lift', 'gain'
            ]
            default_plot = 'confusion_matrix'
        else: # Regression
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
        if st.session_state.model_problem_type == "Classification":
            pcc.plot_model(st.session_state.best_model, plot=plot_choice, display_format='streamlit')
        else:
            pcr.plot_model(st.session_state.best_model, plot=plot_choice, display_format='streamlit')
            