import logging
import os

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def fetch_and_transform_yield_csv_fallback(
    county_name: str,
    state_name: str,
    start_year: int,
    end_year: int,
    csv_path: str | None = None,
) -> pd.DataFrame:
    """
    Reads the bundled CSV for yield data and returns a cleaned DataFrame
    in the same format as the live NASS API path.
    """
    logger.info("Reading local CSV for yield data (%s, %s %d-%d)…", county_name, state_name, start_year, end_year)
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "../../crop_yield_1980-2022.csv")
    df = pd.read_csv(csv_path)
    mask = (
        (df["State"].str.upper() == state_name.upper())
        & (df["County"].str.upper() == county_name.upper())
        & (df["Data Item"].str.contains("YIELD", case=False))
        & (df["Year"] >= start_year)
        & (df["Year"] <= end_year)
    )
    filtered = df[mask]
    if filtered.empty:
        logger.warning("No CSV yield data found for %s, %s %d-%d.", county_name, state_name, start_year, end_year)
        return pd.DataFrame()
    out = (
        filtered[["Year", "Value", "Commodity", "Data Item", "Ag District", "County ANSI"]]
        .rename(
            columns={
                "Value": "CropYield_bu_ac",
                "Commodity": "Crop",
                "Data Item": "DataItem",
                "Ag District": "district",
                "County ANSI": "county_ansi",
            }
        )
        .copy()
    )
    out["CropYield_bu_ac"] = pd.to_numeric(out["CropYield_bu_ac"], errors="coerce")
    out.dropna(subset=["CropYield_bu_ac"], inplace=True)
    out["Year"] = out["Year"].astype(int)
    out["County"] = county_name
    out["State"] = state_name
    if "county_ansi" in out.columns:
        out["county_ansi"] = out["county_ansi"].astype(str).replace("nan", None)
    if "district" in out.columns:
        out["district"] = out["district"].astype(str).replace("nan", None)
    logger.info("CSV yield data loaded: %d rows.", len(out))
    return out


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
