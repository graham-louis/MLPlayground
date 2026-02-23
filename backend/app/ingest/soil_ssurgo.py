import requests
import pandas as pd

def fetch_and_transform_soil(county_name, state_name):
    """
    Fetches and aggregates SSURGO data for an entire county using the USDA SDM API.
    Calculates an area-weighted average of topsoil properties.
    Returns a DataFrame with one row of features, or None if not found.
    """
    print(f"Fetching SSURGO soil data for {county_name}, {state_name}...")
    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    query = f"""
    SELECT
        mu.muacres,
        co.comppct_r,
        ch.ph1to1h2o_r,
        ch.cec7_r,
        ch.sandtotal_r,
        ch.claytotal_r,
        ch.om_r
    FROM sacatalog sc
    LEFT JOIN legend lg ON sc.areasymbol = lg.areasymbol
    LEFT JOIN mapunit mu ON lg.lkey = mu.lkey
    LEFT JOIN component co ON mu.mukey = co.mukey
    LEFT JOIN chorizon ch ON co.cokey = ch.cokey
    WHERE sc.areaname = '{county_name} County, {state_name}'
    AND co.compkind = 'Series'
    AND ch.hzname IN ('Ap', 'A', 'A1')
    """
    try:
        response = requests.post(sdm_api_url, data={"FORMAT": "JSON+COLUMNNAME", "QUERY": query})
        response.raise_for_status()
        data = response.json()
        if 'Table' not in data or len(data['Table']) < 2:
            print(f"  - No soil data found for {county_name}.")
            return None
        soil_df = pd.DataFrame(data['Table'][1:], columns=data['Table'][0])
        numeric_cols = ['muacres', 'comppct_r', 'ph1to1h2o_r', 'cec7_r', 'sandtotal_r', 'claytotal_r', 'om_r']
        for col in numeric_cols:
            soil_df[col] = pd.to_numeric(soil_df[col], errors='coerce')
        soil_df.dropna(inplace=True)
        if soil_df.empty:
            print(f"  - Data for {county_name} was incomplete after cleaning.")
            return None
        soil_df['component_acres'] = (soil_df['comppct_r'] / 100) * soil_df['muacres']
        total_acres = soil_df['component_acres'].sum()
        soil_features = {
            'Soil_pH': (soil_df['ph1to1h2o_r'] * soil_df['component_acres']).sum() / total_acres,
            'Soil_CEC': (soil_df['cec7_r'] * soil_df['component_acres']).sum() / total_acres,
            'PercentSand': (soil_df['sandtotal_r'] * soil_df['component_acres']).sum() / total_acres,
            'PercentClay': (soil_df['claytotal_r'] * soil_df['component_acres']).sum() / total_acres,
            'OM_percent': (soil_df['om_r'] * soil_df['component_acres']).sum() / total_acres,
            'County': county_name,
            'State': state_name
        }
        print(f"Soil data processing complete for {county_name}. ✅")
        return pd.DataFrame([soil_features])
    except requests.exceptions.RequestException as e:
        print(f"  - Failed to get soil data for {county_name}. Error: {e}")
        return None
