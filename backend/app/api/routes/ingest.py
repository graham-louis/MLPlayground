import threading
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import get_session
from app.models import Message, Soil, Yield

router = APIRouter(prefix="/ingest", tags=["ingest"])

_ingest_lock = threading.Lock()
_ingest_running = False
_daily_weather_lock = threading.Lock()
_daily_weather_running = False


class IngestStatus(BaseModel):
    status: Literal["idle", "running"]


class DailyWeatherIngestRequest(BaseModel):
    """Parameters for a Daymet daily-weather fetch into the daily_weather table."""
    state: str
    start_year: int = 2000
    end_year: int = 2022


def _run_ingestion() -> None:
    global _ingest_running
    try:
        from app.ingest.runner import main as run_ingestion
        run_ingestion()
    finally:
        with _ingest_lock:
            _ingest_running = False


def _run_daily_weather_ingest(state: str, start_year: int, end_year: int) -> None:
    """
    Fetch daily weather from the Daymet API for every county in *state*
    (determined from existing Soil rows) and save to the daily_weather table.
    """
    global _daily_weather_running
    import logging
    log = logging.getLogger(__name__)
    try:
        from sqlmodel import create_engine
        from app.core.db import engine
        from app.ingest.climate_nldas import fetch_and_transform_weather, save_daily_weather_to_db

        # Resolve counties from the soil table (populated by the full ingest pipeline).
        with Session(engine) as session:
            soil_rows = session.exec(select(Soil).where(Soil.state == state)).all()
            counties = sorted({s.county for s in soil_rows})

        if not counties:
            # Fall back to counties in the yields table
            with Session(engine) as session:
                yield_rows = session.exec(select(Yield).where(Yield.state == state)).all()
                counties = sorted({y.county for y in yield_rows})

        if not counties:
            log.error("No counties found for state=%s — run the full ingest first.", state)
            return

        log.info("Fetching Daymet daily weather for %d counties in %s (%d–%d)…",
                 len(counties), state, start_year, end_year)

        for i, county in enumerate(counties, 1):
            log.info("[%d/%d] Fetching %s, %s", i, len(counties), county, state)
            try:
                _annual_df, daily_df = fetch_and_transform_weather(
                    county, state, start_year, end_year
                )
                if daily_df is not None and not daily_df.empty:
                    n = save_daily_weather_to_db(daily_df, state)
                    log.info("  → %d rows saved", n)
                else:
                    log.warning("  → no daily data returned for %s", county)
            except Exception as exc:
                log.error("  → failed for %s: %s", county, exc)

        log.info("Daily weather ingest complete for %s.", state)
    finally:
        with _daily_weather_lock:
            _daily_weather_running = False


@router.post("/trigger", response_model=Message)
async def trigger_ingestion(background_tasks: BackgroundTasks) -> Message:
    """
    Trigger the bulk data ingestion pipeline in the background.
    Fetches crop yields from USDA NASS, annual weather from Daymet,
    and soil properties from SSURGO for all configured counties.
    Returns 409 if ingestion is already running.
    """
    global _ingest_running
    with _ingest_lock:
        if _ingest_running:
            raise HTTPException(status_code=409, detail="Ingestion is already running.")
        _ingest_running = True
    background_tasks.add_task(_run_ingestion)
    return Message(message="Data ingestion started in background.")


@router.post("/trigger-daily-weather", response_model=Message)
async def trigger_daily_weather_ingest(
    req: DailyWeatherIngestRequest,
    background_tasks: BackgroundTasks,
) -> Message:
    """
    Fetch daily weather from the Daymet API for every county in *state* and
    store it in the daily_weather table.  Required before running ApsimX
    simulations.  Returns 409 if already running.

    Counties are determined from existing Soil rows for the state; run the
    full ingest pipeline first if the table is empty.
    """
    global _daily_weather_running
    with _daily_weather_lock:
        if _daily_weather_running:
            raise HTTPException(
                status_code=409, detail="Daily weather ingest is already running."
            )
        _daily_weather_running = True
    background_tasks.add_task(
        _run_daily_weather_ingest, req.state, req.start_year, req.end_year
    )
    return Message(
        message=f"Daily weather ingest started for {req.state} ({req.start_year}–{req.end_year})."
    )


@router.get("/status", response_model=IngestStatus)
async def get_ingest_status() -> IngestStatus:
    """Return whether the ingestion pipeline is currently running."""
    return IngestStatus(status="running" if _ingest_running else "idle")
