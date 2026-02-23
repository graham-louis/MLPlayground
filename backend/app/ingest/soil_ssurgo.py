import logging
import re

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Only allow alphanumeric characters, spaces, hyphens, and apostrophes in
# county/state names that are embedded in SQL strings sent to the SDM REST API.
# The SDM endpoint accepts only a plain SQL string (no server-side parameterisation),
# so we validate inputs before interpolation.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9 '\-\.]+$")


def _validate_name(value: str, label: str) -> str:
    """Raise ValueError if *value* contains characters that could alter the SQL query."""
    if not _SAFE_NAME_RE.match(value):
        raise ValueError(f"Unsafe characters in {label}: {value!r}")
    return value


def fetch_and_transform_soil(county_name: str, state_name: str) -> pd.DataFrame | None:
    """
    Fetches and aggregates SSURGO data for an entire county using the USDA SDM API.
    Calculates an area-weighted average of topsoil properties.
    Returns a one-row DataFrame of features, or None if not found.
    """
    county_name = _validate_name(county_name.strip(), "county_name")
    state_name = _validate_name(state_name.strip(), "state_name")

    logger.info("Fetching SSURGO soil data for %s, %s…", county_name, state_name)
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
        response = requests.post(
            sdm_api_url,
            data={"FORMAT": "JSON+COLUMNNAME", "QUERY": query},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if "Table" not in data or len(data["Table"]) < 2:
            logger.warning("No soil data found for %s, %s.", county_name, state_name)
            return None
        soil_df = pd.DataFrame(data["Table"][1:], columns=data["Table"][0])
        numeric_cols = ["muacres", "comppct_r", "ph1to1h2o_r", "cec7_r", "sandtotal_r", "claytotal_r", "om_r"]
        for col in numeric_cols:
            soil_df[col] = pd.to_numeric(soil_df[col], errors="coerce")
        soil_df.dropna(inplace=True)
        if soil_df.empty:
            logger.warning("Soil data for %s was incomplete after cleaning.", county_name)
            return None
        soil_df["component_acres"] = (soil_df["comppct_r"] / 100) * soil_df["muacres"]
        total_acres = soil_df["component_acres"].sum()
        soil_features = {
            "Soil_pH": (soil_df["ph1to1h2o_r"] * soil_df["component_acres"]).sum() / total_acres,
            "Soil_CEC": (soil_df["cec7_r"] * soil_df["component_acres"]).sum() / total_acres,
            "PercentSand": (soil_df["sandtotal_r"] * soil_df["component_acres"]).sum() / total_acres,
            "PercentClay": (soil_df["claytotal_r"] * soil_df["component_acres"]).sum() / total_acres,
            "OM_percent": (soil_df["om_r"] * soil_df["component_acres"]).sum() / total_acres,
            "County": county_name,
            "State": state_name,
        }
        logger.info("Soil data fetched for %s.", county_name)
        return pd.DataFrame([soil_features])
    except requests.RequestException as exc:
        logger.error("Failed to get soil data for %s: %s", county_name, exc)
        return None
