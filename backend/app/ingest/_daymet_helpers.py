"""
Private shared helpers for Daymet and USDA SDM data access.

Prefix underscore = internal module, not a datasource plugin.
"""
import logging
import re
from typing import Optional

import daymetpy
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9 '\-\.]+$")


def _validate_name(value: str, label: str) -> str:
    """Raise ValueError if value contains characters that could alter the SDM SQL string."""
    if not _SAFE_NAME_RE.match(value):
        raise ValueError(f"Unsafe characters in {label}: {value!r}")
    return value


def get_county_center_coord(county_name: str, state_name: str) -> Optional[dict]:
    """
    Return {'lat': float, 'lon': float} for the centre of a county, or None.
    Derived from the USDA SDM bounding-box API.
    """
    county_name = _validate_name(county_name.strip(), "county_name")
    state_name = _validate_name(state_name.strip(), "state_name")

    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    query = f"""
    SELECT mbrminx, mbrminy, mbrmaxx, mbrmaxy
    FROM sacatalog
    WHERE areaname = '{county_name} County, {state_name}'
    """
    try:
        response = requests.post(
            sdm_api_url,
            data={"FORMAT": "JSON", "QUERY": query},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json().get("Table")
        if not data:
            logger.warning("Bounding box not found for %s, %s.", county_name, state_name)
            return None
        min_lon, min_lat, max_lon, max_lat = (float(c) for c in data[0])
        return {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}
    except requests.RequestException as exc:
        logger.error("Error fetching bounding box for %s: %s", county_name, exc)
        return None


def _fill_leap_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daymet provides 365 rows per year, omitting Dec 31 in leap years.
    Insert a synthetic day-366 row (copy of day 365, precipitation = 0).
    Expects columns: year, day_of_year, prcp.
    """
    filled: list[pd.DataFrame] = []
    for year, grp in df.groupby("year"):
        is_leap = (year % 4 == 0) and ((year % 100 != 0) or (year % 400 == 0))
        if is_leap and int(grp["day_of_year"].max()) == 365:
            dec31 = grp[grp["day_of_year"] == 365].copy()
            dec31["day_of_year"] = 366
            dec31["date"] = f"{year}-12-31"
            dec31["prcp"] = 0.0
            filled.append(grp)
            filled.append(dec31)
        else:
            filled.append(grp)
    return pd.concat(filled, ignore_index=True).sort_values(["county", "year", "day_of_year"])


def fetch_daymet_daily(
    county: str,
    state: str,
    start_year: int,
    end_year: int,
) -> Optional[pd.DataFrame]:
    """
    Fetch Daymet daily data for a county centroid.
    Returns a DataFrame with canonical column names suitable for the
    daily_weather datasource, or None on failure.
    """
    coord = get_county_center_coord(county, state)
    if coord is None:
        logger.error("No coordinates for %s, %s — skipping Daymet fetch.", county, state)
        return None

    try:
        raw = daymetpy.daymet_timeseries(
            lon=coord["lon"], lat=coord["lat"],
            start_year=start_year, end_year=end_year,
        )
    except Exception as exc:
        logger.error("Daymet fetch failed for %s, %s: %s", county, state, exc)
        return None

    raw.rename(columns={"year": "year", "yday": "day_of_year"}, inplace=True)
    raw["date"] = pd.to_datetime(
        raw[["year", "day_of_year"]].astype(str).agg("-".join, axis=1),
        format="%Y-%j",
    ).dt.strftime("%Y-%m-%d")
    raw["county"] = county
    raw["state"] = state

    df = raw[["year", "day_of_year", "date", "state", "county",
              "tmax", "tmin", "prcp", "srad", "vp", "dayl"]].copy()
    return _fill_leap_days(df)


def fetch_daymet_annual(
    county: str,
    state: str,
    start_year: int,
    end_year: int,
) -> Optional[pd.DataFrame]:
    """
    Fetch Daymet data and aggregate to growing-season annual summaries.
    Returns a DataFrame with canonical column names suitable for the
    weather datasource (one row per year), or None on failure.
    """
    daily = fetch_daymet_daily(county, state, start_year, end_year)
    if daily is None or daily.empty:
        return None

    daily["date_dt"] = pd.to_datetime(daily["date"])
    rows = []
    for year in range(start_year, end_year + 1):
        yr = daily[daily["year"] == year]
        if yr.empty:
            continue
        gs = yr[yr["date_dt"].dt.month.between(5, 9)]
        t_avg = (gs["tmax"] + gs["tmin"]) / 2
        gdd = (t_avg - 10).clip(lower=0)
        rows.append({
            "year": year,
            "state": state,
            "county": county,
            "avg_temp": round(float(t_avg.mean()), 4) if not t_avg.empty else None,
            "precipitation": round(float(gs["prcp"].sum()), 4) if not gs.empty else None,
            "gdd": round(float(gdd.sum()), 4) if not gdd.empty else None,
            "vp": round(float(gs["vp"].mean()), 4) if not gs.empty else None,
            "srad": round(float(gs["srad"].mean()), 4) if not gs.empty else None,
        })
    return pd.DataFrame(rows) if rows else None


def fetch_ssurgo_soil(county: str, state: str) -> Optional[pd.DataFrame]:
    """
    Fetch SSURGO area-weighted topsoil properties for a county.
    Returns a one-row DataFrame with canonical column names, or None on failure.
    """
    county = _validate_name(county.strip(), "county_name")
    state = _validate_name(state.strip(), "state_name")

    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    query = f"""
    SELECT
        mu.muacres,
        co.comppct_r,
        ch.ph1to1h2o_r,
        ch.sandtotal_r,
        ch.claytotal_r,
        ch.om_r
    FROM sacatalog sc
    LEFT JOIN legend lg ON sc.areasymbol = lg.areasymbol
    LEFT JOIN mapunit mu ON lg.lkey = mu.lkey
    LEFT JOIN component co ON mu.mukey = co.mukey
    LEFT JOIN chorizon ch ON co.cokey = ch.cokey
    WHERE sc.areaname = '{county} County, {state}'
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
            logger.warning("No soil data found for %s, %s.", county, state)
            return None
        soil_df = pd.DataFrame(data["Table"][1:], columns=data["Table"][0])
        numeric_cols = ["muacres", "comppct_r", "ph1to1h2o_r", "sandtotal_r", "claytotal_r", "om_r"]
        for col in numeric_cols:
            soil_df[col] = pd.to_numeric(soil_df[col], errors="coerce")
        soil_df.dropna(inplace=True)
        if soil_df.empty:
            logger.warning("Soil data incomplete for %s, %s.", county, state)
            return None
        soil_df["component_acres"] = (soil_df["comppct_r"] / 100) * soil_df["muacres"]
        total = soil_df["component_acres"].sum()
        return pd.DataFrame([{
            "state": state,
            "county": county,
            "ph": round((soil_df["ph1to1h2o_r"] * soil_df["component_acres"]).sum() / total, 4),
            "organic_matter": round((soil_df["om_r"] * soil_df["component_acres"]).sum() / total, 4),
            "sand_pct": round((soil_df["sandtotal_r"] * soil_df["component_acres"]).sum() / total, 4),
            "clay_pct": round((soil_df["claytotal_r"] * soil_df["component_acres"]).sum() / total, 4),
        }])
    except requests.RequestException as exc:
        logger.error("Failed to get soil data for %s, %s: %s", county, state, exc)
        return None


def get_counties_for_state(state_name: str) -> list[str]:
    """Query USDA SDM for all county names in a state."""
    state_name = _validate_name(state_name.strip(), "state_name")
    sdm_api_url = "https://sdmdataaccess.nrcs.usda.gov/tabular/post.rest"
    query = f"SELECT areaname FROM sacatalog WHERE areaname LIKE '%, {state_name}'"
    try:
        response = requests.post(sdm_api_url, data={"FORMAT": "JSON", "QUERY": query}, timeout=30)
        response.raise_for_status()
        data = response.json().get("Table", [])
        if len(data) < 2:
            return []
        return sorted(row[0].split(" County,")[0] for row in data[1:])
    except requests.RequestException as exc:
        logger.error("Error fetching county list for %s: %s", state_name, exc)
        return []
