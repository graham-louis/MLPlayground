"""
=============================================================================
NEW DATASOURCE TEMPLATE — MLPlayground
=============================================================================

This file is a copy-paste starting point for adding a new data source.
Every section that needs your input is marked with "# TODO".

HOW TO USE THIS FILE
1. Copy it to a new name, e.g.:  satellite_ndvi.py
2. Work through every # TODO comment below.
3. Follow the "What to do next" guide at the bottom of this file.

WHAT THIS TEMPLATE DOES
It shows you exactly how to write a Python function that fetches data
from an external source and returns it as a standard table (DataFrame)
that MLPlayground can store and display.

You do NOT need to understand FastAPI, SQLAlchemy, or React.
You only need to fill in the TODO sections in this one file,
then follow the 4 follow-up steps described at the bottom.

EXAMPLE USE CASE
Imagine you want to add NDVI (satellite vegetation index) data from NASA.
The comments below use that as a running example.
=============================================================================
"""

# ---------------------------------------------------------------------------
# IMPORTS  (leave these alone unless you need extra libraries)
# ---------------------------------------------------------------------------
import logging
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TODO 1 — Name your data source
# ---------------------------------------------------------------------------
# Replace "MyDataSource" with a short name for your source.
# Example: "SatelliteNDVI", "DroughtIndex", "PestPressure"

DATASOURCE_NAME = "MyDataSource"   # TODO: change this

# ---------------------------------------------------------------------------
# TODO 2 — Describe your data source
# ---------------------------------------------------------------------------
# This text shows up in the UI and documentation.

DATASOURCE_DESCRIPTION = (
    "A short description of what this data source provides and "
    "why it is useful for crop yield prediction."
)   # TODO: change this

# ---------------------------------------------------------------------------
# TODO 3 — Define the columns your data returns
# ---------------------------------------------------------------------------
# List every column your function will return.
# The first four ("year", "state", "county", "source") are REQUIRED.
# Add your own domain columns after them.
#
# Example for NDVI:
#   DATASOURCE_COLUMNS = ["year", "state", "county", "source",
#                          "ndvi_mean", "ndvi_min", "ndvi_max"]

DATASOURCE_COLUMNS: list[str] = [
    "year",
    "state",
    "county",
    "source",
    # TODO: add your columns here, e.g.:
    # "my_metric_1",
    # "my_metric_2",
]


# ---------------------------------------------------------------------------
# MAIN FETCH FUNCTION — this is the only function you must implement
# ---------------------------------------------------------------------------

def fetch_and_transform(
    county_name: str,
    state_name: str,
    start_year: int,
    end_year: int,
) -> Optional[pd.DataFrame]:
    """
    Fetch data for a single county/state over a range of years.

    Parameters
    ----------
    county_name : str
        The name of the county, e.g. "Wake".
    state_name : str
        The full state name, e.g. "North Carolina".
    start_year : int
        First year to fetch (inclusive).
    end_year : int
        Last year to fetch (inclusive).

    Returns
    -------
    pd.DataFrame
        A table with columns matching DATASOURCE_COLUMNS.
        Return None or an empty DataFrame if no data is available.

    Notes
    -----
    • The runner will call this function once per county, per state.
    • Any exception you raise will be caught and logged — the pipeline
      will continue with the next county.
    • Keep network calls efficient: fetch multiple years in one request
      where the API supports it.
    """
    logger.info(
        "Fetching %s data for %s, %s (%d–%d)...",
        DATASOURCE_NAME, county_name, state_name, start_year, end_year,
    )

    # TODO 4 — Replace this block with your actual data fetching logic.
    #
    # You have three common options:
    #
    # OPTION A — Call a REST API
    # --------------------------
    # url = "https://example.com/api/data"
    # params = {
    #     "county": county_name,
    #     "state": state_name,
    #     "start": start_year,
    #     "end": end_year,
    # }
    # response = requests.get(url, params=params, timeout=30)
    # response.raise_for_status()            # raises an error if request failed
    # data = response.json()["results"]      # adapt to the API's JSON structure
    # df = pd.DataFrame(data)
    #
    # OPTION B — Read a local file (CSV / Excel)
    # -------------------------------------------
    # df = pd.read_csv("/data/my_dataset.csv")
    # df = df[(df["county"] == county_name) & (df["year"].between(start_year, end_year))]
    #
    # OPTION C — Build the data manually (for testing)
    # -------------------------------------------------
    # rows = []
    # for year in range(start_year, end_year + 1):
    #     rows.append({
    #         "year": year,
    #         "county": county_name,
    #         "state": state_name,
    #         "my_metric": 42.0,    # replace with real computation
    #     })
    # df = pd.DataFrame(rows)

    # ---- PLACEHOLDER (delete this once you fill in your logic above) ----
    logger.warning(
        "%s: fetch_and_transform is not yet implemented. "
        "Edit backend/app/ingest/%s.py to add your data-fetching logic.",
        DATASOURCE_NAME, __name__.split(".")[-1],
    )
    return None
    # ---- END PLACEHOLDER ----

    # TODO 5 — Normalise the DataFrame before returning it.
    #
    # Whatever you fetched above, make sure the returned DataFrame has:
    # • A "year"    column (integer)
    # • A "county"  column (string, matching the county_name parameter)
    # • A "state"   column (string, matching the state_name parameter)
    # • A "source"  column (string, set to DATASOURCE_NAME — done below)
    # • All numeric columns as float (use pd.to_numeric(..., errors="coerce"))
    #
    # Example clean-up block:
    # df["year"] = df["year"].astype(int)
    # df["county"] = county_name
    # df["state"] = state_name
    # df["source"] = DATASOURCE_NAME
    # df["my_metric"] = pd.to_numeric(df["my_metric"], errors="coerce")
    # df = df.dropna(subset=["my_metric"])   # drop rows where your key metric is missing
    # return df[DATASOURCE_COLUMNS]          # return only the declared columns


# =============================================================================
# WHAT TO DO NEXT — 4 follow-up steps (each takes < 10 minutes)
# =============================================================================
#
# After you have the function above returning real data, do the following:
#
# STEP 1 — Add a database model  (backend/app/db_models.py)
# -------------------------------------------------------
# Add a SQLModel class for your table.  Copy the Weather block as a template:
#
#   class MyDataSource(SQLModel, table=True):
#       __tablename__ = "my_datasource"
#       id: Optional[int] = Field(default=None, primary_key=True)
#       year: int
#       state: str
#       county: str
#       source: str = DATASOURCE_NAME
#       # add your columns here:
#       my_metric: Optional[float] = None
#
#   class MyDataSourcePublic(MyDataSource):
#       id: int
#
#   class MyDataSourcesPublic(SQLModel):
#       data: list[MyDataSourcePublic]
#       count: int
#
#
# STEP 2 — Generate a database migration  (inside the running Docker container)
# ------------------------------------------------------------------------------
# Run these two commands in a terminal:
#
#   docker compose exec backend alembic revision --autogenerate -m "Add my_datasource table"
#   docker compose exec backend alembic upgrade head
#
# That's it — the table will be created automatically.
#
#
# STEP 3 — Write an upsert function and register with the datasource registry
# ---------------------------------------------------------------------------
# Add an upsert function in backend/app/ingest/runner.py (copy upsert_soil_to_db
# as a template):
#
#   def upsert_my_datasource_to_db(df: pd.DataFrame) -> None:
#       from app.db_models import MyDataSource
#       if df is None or df.empty:
#           return
#       with Session(engine) as session:
#           for _, row in df.iterrows():
#               obj = session.exec(
#                   select(MyDataSource).where(
#                       MyDataSource.year == int(row["year"]),
#                       MyDataSource.county == row["county"],
#                       MyDataSource.state == row["state"],
#                   )
#               ).first()
#               if obj is None:
#                   obj = MyDataSource(year=int(row["year"]), county=row["county"], state=row["state"])
#               obj.my_metric = row.get("my_metric")
#               session.add(obj)
#           session.commit()
#
# Then register with the datasource registry by adding the following at the
# bottom of THIS file (my_source.py), passing BOTH fetch_fn and upsert_fn:
#
#   from app.ingest.registry import DATASOURCE_REGISTRY
#   from app.ingest.runner import upsert_my_datasource_to_db
#
#   DATASOURCE_REGISTRY.register(
#       key=DATASOURCE_NAME,
#       label="My Data Source",
#       endpoint="/api/v1/my_datasource/",
#       columns=DATASOURCE_COLUMNS,
#       scope_params=[
#           {"name": "states",     "type": "string_list", "label": "States", "default": ["North Carolina"]},
#           {"name": "start_year", "type": "integer",     "label": "Start Year", "default": 1980},
#           {"name": "end_year",   "type": "integer",     "label": "End Year",   "default": 2022},
#       ],
#       fetch_fn=fetch_and_transform,
#       upsert_fn=upsert_my_datasource_to_db,   # ← REQUIRED for ingest to persist data
#       description=DATASOURCE_DESCRIPTION,
#   )
#
# The ingest pipeline calls fetch_fn to get the DataFrame, then upsert_fn to
# save it.  If upsert_fn is missing, the data will be fetched but NOT saved.
#
#
# STEP 4 — Add an API route  (backend/app/api/routes/ — copy weather.py)
# -----------------------------------------------------------------------
# Copy backend/app/api/routes/weather.py to my_datasource.py.
# Replace "Weather" with your model class name and adjust the query filters.
# Then open backend/app/api/main.py and add TWO lines:
#
#   from app.api.routes import my_datasource
#   import app.ingest.my_datasource          # noqa: F401 — registers datasource at startup
#   api_router.include_router(my_datasource.router)
#
# The second import is REQUIRED so the DATASOURCE_REGISTRY.register() call
# runs when the app boots — without it the datasource won't appear in the
# Data Explorer or Ingest form even though the API route works fine.
#
# After that your new data source will automatically appear in the API docs
# at http://localhost:8000/docs and can be queried from the Data Explorer.
# =============================================================================
