import logging
import re

import daymetpy
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9 '\-\.]+$")


def _validate_name(value: str, label: str) -> str:
    """Raise ValueError if *value* contains characters that could alter the SQL query."""
    if not _SAFE_NAME_RE.match(value):
        raise ValueError(f"Unsafe characters in {label}: {value!r}")
    return value


def get_county_bbox(county_name: str, state_name: str) -> tuple | None:
    """
    Queries the USDA SDM API to get the bounding box for a specific county.

    Returns:
        A tuple of (min_lon, min_lat, max_lon, max_lat) or None if not found.
    """
    county_name = _validate_name(county_name.strip(), "county_name")
    state_name = _validate_name(state_name.strip(), "state_name")

    logger.debug("Fetching bounding box for %s, %s...", county_name, state_name)
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
        coords = data[0]
        return tuple(float(c) for c in coords)
    except requests.RequestException as exc:
        logger.error("Error fetching bounding box for %s: %s", county_name, exc)
        return None


def get_county_center_coord(county_name: str, state_name: str) -> dict | None:
    """
    Returns the centre lat/lon for a county, derived from its bounding box.

    Returns:
        ``{'lat': float, 'lon': float}`` or ``None`` if the bounding box cannot be found.
    """
    bbox = get_county_bbox(county_name, state_name)
    if not bbox:
        return None
    min_lon, min_lat, max_lon, max_lat = bbox
    center = {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}
    logger.debug("Center for %s: lat=%.4f lon=%.4f", county_name, center["lat"], center["lon"])
    return center


def fetch_and_transform_weather(
    county_name: str,
    state_name: str,
    start_year: int,
    end_year: int,
) -> tuple:
    """
    Fetches Daymet daily weather data for the county centroid, engineers growing-season
    features, and returns ``(annual_df, daily_df)``.  Either value may be ``None`` on failure.
    """
    coord = get_county_center_coord(county_name, state_name)
    if coord is None:
        logger.error("Cannot fetch Daymet data: no coordinates for %s, %s.", county_name, state_name)
        return None, None

    lon, lat = coord["lon"], coord["lat"]
    logger.info("Fetching Daymet weather for %s, %s (%d-%d)...", county_name, state_name, start_year, end_year)

    try:
        all_daily_weather = daymetpy.daymet_timeseries(lon=lon, lat=lat, start_year=start_year, end_year=end_year)
    except Exception as exc:
        logger.error("Daymet fetch failed for %s: %s", county_name, exc)
        return None, None

    all_daily_weather.rename(columns={"year": "Year", "yday": "DayOfYear"}, inplace=True)
    all_daily_weather["date"] = pd.to_datetime(
        all_daily_weather[["Year", "DayOfYear"]].astype(str).agg("-".join, axis=1),
        format="%Y-%j",
    )

    if all_daily_weather.empty:
        logger.warning("No Daymet data returned for %s.", county_name)
        return None, None

    all_daily_weather["Year"] = all_daily_weather["date"].dt.year
    all_daily_weather["County"] = county_name

    all_years_weather = []
    for year in range(start_year, end_year + 1):
        yearly_data = all_daily_weather[all_daily_weather["Year"] == year]
        if yearly_data.empty:
            logger.warning("No Daymet data for %s in %d.", county_name, year)
            continue
        growing_season = yearly_data[yearly_data["date"].dt.month.between(5, 9)]
        t_avg = (growing_season["tmax"] + growing_season["tmin"]) / 2
        gdd = (t_avg - 10).clip(lower=0)
        all_years_weather.append(
            {
                "Year": year,
                "TotalPrecip_mm": growing_season["prcp"].sum(),
                "AvgTemp_C": t_avg.mean(),
                "TotalGDD": gdd.sum(),
                "County": county_name,
                "State": state_name,
                "vp": growing_season["vp"].mean(),
                "srad": growing_season["srad"].mean(),
            }
        )

    logger.info("Daymet weather processed for %s: %d years.", county_name, len(all_years_weather))
    annual_df = pd.DataFrame(all_years_weather)
    return annual_df, all_daily_weather
