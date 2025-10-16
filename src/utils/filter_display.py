import streamlit as st

def display_selected_filters():
    """
    Display the currently selected filters (crop and year range) in a consistent format.
    Shows 'Not selected' if no filters have been chosen.
    """
    # Create a container for the filter display
    with st.container():
        st.markdown("---")
        st.subheader("📊 Selected Filters")
        
        # Get selected crop
        selected_crop = st.session_state.get('selected_crop', None)
        crop_display = selected_crop if selected_crop else "Not selected"
        
        # Get selected year range
        selected_year_range = st.session_state.get('selected_year_range', None)
        if selected_year_range:
            year_display = f"{selected_year_range[0]} - {selected_year_range[1]}"
        else:
            year_display = "Not selected"
        
        # Display filters in columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("🌾 Crop", crop_display)
        
        with col2:
            st.metric("📅 Year Range", year_display)
        
        st.markdown("---")

def display_filters_in_sidebar():
    """
    Display the currently selected filters in the sidebar for easy reference.
    """
    st.sidebar.markdown("### 🔍 Current Selection")
    
    # Get selected crop
    selected_crop = st.session_state.get('selected_crop', None)
    crop_display = selected_crop if selected_crop else "Not selected"
    
    # Get selected year range
    selected_year_range = st.session_state.get('selected_year_range', None)
    if selected_year_range:
        year_display = f"{selected_year_range[0]} - {selected_year_range[1]}"
    else:
        year_display = "Not selected"
    
    st.sidebar.write(f"**Crop:** {crop_display}")
    st.sidebar.write(f"**Years:** {year_display}")
    
    # Add a note if no data is loaded
    if 'df' not in st.session_state:
        st.sidebar.warning("⚠️ No data loaded yet. Please go to 'Select Data' page first.")
