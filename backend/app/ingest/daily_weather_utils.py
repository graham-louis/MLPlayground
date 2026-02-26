"""
Daily weather DB utilities for MLPlayground.

Provides the helper functions used by climate_nldas to persist Daymet daily
weather into the ``daily_weather`` table.  All data is sourced from the
Daymet API via climate_nldas — no CSV files are used anywhere.

Key helpers:
  _fill_leap_days(df)              — fills missing Dec 31 in Daymet leap years
  bulk_load_daily_weather(df, st)  — fast county-bulk delete + insert
  upsert_daily_weather(df, st)     — row-by-row upsert (slower, used for small updates)
"""
import logging
from typing import Optional

import pandas as pd
from sqlmodel import Session, select

from app.core.db import engine
from app.models import DailyWeather

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Leap-year gap filling
# ---------------------------------------------------------------------------

def _fill_leap_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daymet provides exactly 365 rows per year, omitting Dec 31 in leap years.
    Inserts a synthetic day 366 row (copy of day 365, precipitation = 0) so
    every year has a complete consecutive date sequence that ApsimX requires.
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


# ---------------------------------------------------------------------------
# Row-by-row upsert (used for small, incremental updates)
# ---------------------------------------------------------------------------

def upsert_daily_weather(df: pd.DataFrame, state: str) -> int:
    """Upsert daily weather rows from *df* into the DB. Returns rows processed."""
    count = 0
    with Session(engine) as session:
        for _, row in df.iterrows():
            existing = session.exec(
                select(DailyWeather).where(
                    DailyWeather.county == row["County"],
                    DailyWeather.state == state,
                    DailyWeather.year == int(row["Year"]),
                    DailyWeather.day_of_year == int(row["DayOfYear"]),
                )
            ).first()

            if existing is None:
                existing = DailyWeather(
                    county=row["County"],
                    state=state,
                    year=int(row["Year"]),
                    day_of_year=int(row["DayOfYear"]),
                    date=str(row["date"]),
                )

            existing.tmax = float(row["tmax"]) if pd.notna(row.get("tmax")) else None
            existing.tmin = float(row["tmin"]) if pd.notna(row.get("tmin")) else None
            existing.prcp = float(row["prcp"]) if pd.notna(row.get("prcp")) else None
            existing.srad = float(row["srad"]) if pd.notna(row.get("srad")) else None
            existing.vp   = float(row["vp"])   if pd.notna(row.get("vp"))   else None
            existing.dayl = float(row["dayl"]) if pd.notna(row.get("dayl")) else None
            session.add(existing)
            count += 1

        session.commit()
    return count


# ---------------------------------------------------------------------------
# Bulk load (fast: delete existing rows then bulk insert per county)
# ---------------------------------------------------------------------------

def bulk_load_daily_weather(df: pd.DataFrame, state: str) -> int:
    """
    Fast bulk load: for each county, delete existing rows in the year range
    then bulk insert.  Much faster than row-by-row upsert for large loads.
    Returns the total number of rows inserted.
    """
    from sqlalchemy import delete as sa_delete

    count = 0
    counties = df["County"].unique()
    years = sorted(df["Year"].unique())
    year_min, year_max = int(years[0]), int(years[-1])

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
                    date=str(r["date"]),
                    tmax=float(r["tmax"]) if pd.notna(r.get("tmax")) else None,
                    tmin=float(r["tmin"]) if pd.notna(r.get("tmin")) else None,
                    prcp=float(r["prcp"]) if pd.notna(r.get("prcp")) else None,
                    srad=float(r["srad"]) if pd.notna(r.get("srad")) else None,
                    vp=float(r["vp"])     if pd.notna(r.get("vp"))   else None,
                    dayl=float(r["dayl"]) if pd.notna(r.get("dayl")) else None,
                )
                for _, r in county_df.iterrows()
            ]
            session.add_all(objects)
            count += len(objects)
        session.commit()
    return count
