import logging
import re

import daymetpy
import pandas as pd
import requests
from sqlalchemy import delete as sa_delete
from sqlmodel import Session

from app.core.db import engine
from app.db_models import DailyWeather

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


def _fill_leap_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daymet provides exactly 365 rows per year, omitting Dec 31 in leap years.
    Inserts a synthetic day 366 row (copy of day 365, precipitation = 0) so
    every year has a complete consecutive date sequence.
    """
    filled: list[pd.DataFrame] = []
    for year, grp in df.groupby("Year"):
        is_leap = (year % 4 == 0) and ((year % 100 != 0) or (year % 400 == 0))
        if is_leap and int(grp["DayOfYear"].max()) == 365:
            dec31 = grp[grp["DayOfYear"] == 365].copy()
            dec31["DayOfYear"] = 366
            dec31["date"] = f"{year}-12-31"
            dec31["prcp"] = 0.0
            filled.append(grp)
            filled.append(dec31)
        else:
            filled.append(grp)
    return pd.concat(filled, ignore_index=True).sort_values(["County", "Year", "DayOfYear"])


def save_daily_weather_to_db(daily_df: pd.DataFrame, state: str) -> int:
    """
    Persist a Daymet daily DataFrame (as returned by ``fetch_and_transform_weather``)
    into the ``daily_weather`` table.

    For each county the existing rows in the covered year range are deleted then
    bulk-inserted, which is much faster than row-by-row upsert.

    Args:
        daily_df: DataFrame with columns Year, DayOfYear, date, County,
                  tmax, tmin, prcp, srad, vp, dayl.
        state:    State name to store alongside each row (e.g. "North Carolina").

    Returns:
        Total number of rows written to the DB.
    """
    df = _fill_leap_days(daily_df)
    counties = df["County"].unique()
    years = sorted(df["Year"].unique())
    year_min, year_max = int(years[0]), int(years[-1])
    count = 0

    with Session(engine) as session:
        for county in counties:
            session.exec(  # type: ignore[call-overload]
                sa_delete(DailyWeather).where(
                    DailyWeather.county == county,
                    DailyWeather.state == state,
                    DailyWeather.year >= year_min,
                    DailyWeather.year <= year_max,
                )
            )
            county_df = df[df["County"] == county]
            objects = [
                DailyWeather(
                    county=county,
                    state=state,
                    year=int(r["Year"]),
                    day_of_year=int(r["DayOfYear"]),
                    date=str(r["date"].date() if hasattr(r["date"], "date") else r["date"]),
                    tmax=float(r["tmax"]) if pd.notna(r.get("tmax")) else None,
                    tmin=float(r["tmin"]) if pd.notna(r.get("tmin")) else None,
                    prcp=float(r["prcp"]) if pd.notna(r.get("prcp")) else None,
                    srad=float(r["srad"]) if pd.notna(r.get("srad")) else None,
                    vp=float(r["vp"]) if pd.notna(r.get("vp")) else None,
                    dayl=float(r["dayl"]) if pd.notna(r.get("dayl")) else None,
                )
                for _, r in county_df.iterrows()
            ]
            session.add_all(objects)
            count += len(objects)
        session.commit()

    logger.info("Saved %d daily weather rows to DB for state=%s.", count, state)
    return count


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
