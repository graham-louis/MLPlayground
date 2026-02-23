import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def fetch_and_transform_yield(
    api_key: str,
    county_name: str,
    state_name: str,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    Fetches annual crop yield data from the USDA NASS QuickStats API.
    Returns a cleaned DataFrame, or an empty DataFrame on failure.
    """
    logger.info("Fetching USDA NASS yield data (%s, %s %d-%d)…", county_name, state_name, start_year, end_year)
    if not api_key or api_key == "YOUR_API_KEY":
        logger.error("Valid USDA NASS API key required.")
        return pd.DataFrame()
    base_url = "https://quickstats.nass.usda.gov/api/api_GET/"  # HTTPS supported since 2020
    params = {
        "key": api_key,
        "source_desc": "SURVEY",
        "sector_desc": "CROPS",
        "group_desc": "FIELD CROPS",
        "statisticcat_desc": "YIELD",
        "unit_desc": "BU / ACRE",
        "agg_level_desc": "COUNTY",
        "state_name": state_name.upper(),
        "county_name": county_name.upper(),
        "year__LE": end_year,
        "year__GE": start_year,
        "format": "JSON",
    }
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("NASS API request failed: %s", exc)
        return pd.DataFrame()

    data = response.json().get("data", [])
    if not data:
        logger.warning("No yield data returned from NASS for %s, %s.", county_name, state_name)
        return pd.DataFrame()

    yield_df = pd.DataFrame(data)
    if "commodity_desc" in yield_df.columns:
        cols = ["year", "Value", "commodity_desc", "asd_desc", "county_ansi", "unit_desc"]
        yield_df = yield_df[[c for c in cols if c in yield_df.columns]].rename(
            columns={
                "year": "Year",
                "Value": "CropYield_bu_ac",
                "commodity_desc": "Crop",
                "asd_desc": "district",
                "unit_desc": "unit",
            }
        )
    else:
        yield_df = yield_df[["year", "Value"]].rename(columns={"year": "Year", "Value": "CropYield_bu_ac"})

    if yield_df["CropYield_bu_ac"].dtype == object:
        yield_df["CropYield_bu_ac"] = yield_df["CropYield_bu_ac"].str.replace(",", "", regex=False)
    yield_df["CropYield_bu_ac"] = pd.to_numeric(yield_df["CropYield_bu_ac"], errors="coerce")
    yield_df.dropna(inplace=True)
    yield_df["Year"] = yield_df["Year"].astype(int)
    yield_df["County"] = county_name
    yield_df["State"] = state_name
    logger.info("NASS yield data fetched: %d rows.", len(yield_df))
    return yield_df
