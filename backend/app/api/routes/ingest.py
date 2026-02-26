"""
Ingestion orchestration endpoints for MLPlayground.

Provides:
  POST /api/v1/ingest/run          — generic ingest for any registered datasource
  GET  /api/v1/ingest/status/{id}  — poll job progress
  POST /api/v1/ingest/trigger             — legacy full-pipeline trigger
  GET  /api/v1/ingest/status              — legacy idle/running flag
  POST /api/v1/ingest/trigger-daily-weather — Daymet daily-weather ingest
"""
import logging
import threading
import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import engine
from app.db_models import Message, Soil, Yield

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory job store (process-local; suitable for single-worker deployments)
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# Legacy single-job flags for the /trigger + /status (no job_id) endpoints
_ingest_lock = threading.Lock()
_ingest_running = False
_daily_weather_lock = threading.Lock()
_daily_weather_running = False


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IngestRunRequest(BaseModel):
    """
    Generic ingest request.

    ``sources`` — list of registered datasource keys (e.g. ``["yields", "weather"]``).
    ``scope``   — arbitrary key/value filter dict passed to each source's fetch function.
                  Common keys: ``states`` (list[str]), ``start_year``, ``end_year``.
    """
    sources: list[str]
    scope: dict = {}


class IngestJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    progress: float = 0.0     # 0.0 – 1.0
    message: str = ""
    errors: list[str] = []


class IngestStatus(BaseModel):
    status: Literal["idle", "running"]


class DailyWeatherIngestRequest(BaseModel):
    state: str
    start_year: int = 2000
    end_year: int = 2022


# ---------------------------------------------------------------------------
# Generic run / status
# ---------------------------------------------------------------------------

def _run_generic_ingest(job_id: str, sources: list[str], scope: dict) -> None:
    """Background worker for the generic /run endpoint."""
    from app.ingest.registry import DATASOURCE_REGISTRY
    from app.ingest.runner import (
        get_counties_for_state,
        upsert_soil_to_db,
        upsert_weather_to_db,
        upsert_yield_to_db,
        upsert_weather_psa_to_db,
    )
    from app.ingest.weather_daymet import fetch_and_transform_weather, save_daily_weather_to_db
    from app.ingest.yields_nass import fetch_and_transform_yield
    from app.ingest.soil_ssurgo import fetch_and_transform_soil
    from app.ingest.weather_psa import fetch_and_transform
    from app.core.config import settings

    errors: list[str] = []
    total_steps = max(len(sources), 1)
    step = 0

    def _update(status: str, msg: str, progress: float) -> None:
        with _jobs_lock:
            _jobs[job_id].update(status=status, message=msg, progress=progress, errors=errors)

    _update("running", "Starting…", 0.0)

    states: list[str] = scope.get("states", ["North Carolina"])
    if isinstance(states, str):
        states = [s.strip() for s in states.split(",") if s.strip()]
    start_year: int = int(scope.get("start_year", 1980))
    end_year:   int = int(scope.get("end_year", 2022))

    for source_key in sources:
        entry = DATASOURCE_REGISTRY.get(source_key)
        if entry is None:
            errors.append(f"Unknown datasource key: {source_key!r}")
            step += 1
            _update("running", f"Skipped unknown source '{source_key}'", step / total_steps)
            continue

        for state in states:
            counties = get_counties_for_state(state)
            county_total = max(len(counties), 1)
            for c_idx, county in enumerate(counties, 1):
                try:
                    if source_key == "yields":
                        api_key = settings.NASS_API_KEY
                        if not api_key:
                            errors.append("NASS_API_KEY not set — skipping yields ingest.")
                            break
                        df = fetch_and_transform_yield(api_key, county, state, start_year, end_year)
                        upsert_yield_to_db(df)

                    elif source_key == "weather":
                        result = fetch_and_transform_weather(county, state, start_year, end_year)
                        wdf, ddf = result if isinstance(result, tuple) else (result, None)
                        upsert_weather_to_db(wdf)
                        if ddf is not None and not ddf.empty:
                            save_daily_weather_to_db(ddf, state)

                    elif source_key == "daily_weather":
                        _, ddf = fetch_and_transform_weather(county, state, start_year, end_year)
                        if ddf is not None and not ddf.empty:
                            save_daily_weather_to_db(ddf, state)

                    elif source_key == "soil":
                        df = fetch_and_transform_soil(county, state)
                        upsert_soil_to_db(df)

                    else:
                        # Generic path for datasources registered outside the four bundled sources.
                        # fetch_fn fetches the data; upsert_fn persists it to the DB.
                        if entry.fetch_fn is None:
                            errors.append(f"{source_key}: no fetch_fn registered — cannot ingest.")
                        elif entry.upsert_fn is None:
                            errors.append(f"{source_key}: no upsert_fn registered — data fetched but not saved.")
                        else:
                            df = entry.fetch_fn(county, state, start_year, end_year)
                            entry.upsert_fn(df)

                except Exception as exc:
                    errors.append(f"{source_key}/{county},{state}: {exc}")
                    logger.error("Ingest error for %s/%s,%s: %s", source_key, county, state, exc)

                progress = (step + c_idx / county_total) / total_steps
                _update("running", f"{source_key}: {county}, {state} ({c_idx}/{county_total})", progress)

        step += 1
        _update("running", f"Completed {source_key}", step / total_steps)

    final_status = "error" if errors and not any(True for _ in sources) else "done"
    _update("done", "Ingestion complete.", 1.0)


@router.post("/run", response_model=IngestJobStatus)
async def run_ingest(
    req: IngestRunRequest,
    background_tasks: BackgroundTasks,
) -> IngestJobStatus:
    """
    Trigger ingestion for any combination of registered datasources.

    Dispatches each source's fetch function in a background task and returns
    a ``job_id`` you can use with ``GET /status/{job_id}`` to poll progress.
    """
    if not req.sources:
        raise HTTPException(status_code=422, detail="At least one source must be specified.")

    from app.ingest.registry import DATASOURCE_REGISTRY
    unknown = [s for s in req.sources if DATASOURCE_REGISTRY.get(s) is None]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown datasource keys: {unknown}")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "message": "Queued",
            "errors": [],
        }

    background_tasks.add_task(_run_generic_ingest, job_id, req.sources, req.scope)
    return IngestJobStatus(job_id=job_id, status="queued", message="Queued")


@router.get("/status/{job_id}", response_model=IngestJobStatus)
async def get_job_status(job_id: str) -> IngestJobStatus:
    """Poll the status of a running or completed ingest job."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return IngestJobStatus(**job)


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backwards compatibility with explore.tsx)
# ---------------------------------------------------------------------------

def _run_ingestion() -> None:
    global _ingest_running
    try:
        from app.ingest.runner import main as run_ingestion
        run_ingestion()
    finally:
        with _ingest_lock:
            _ingest_running = False


def _run_daily_weather_ingest(state: str, start_year: int, end_year: int) -> None:
    global _daily_weather_running
    try:
        from app.ingest.weather_daymet import fetch_and_transform_weather, save_daily_weather_to_db

        with Session(engine) as session:
            soil_rows = session.exec(select(Soil).where(Soil.state == state)).all()
            counties = sorted({s.county for s in soil_rows})

        if not counties:
            with Session(engine) as session:
                yield_rows = session.exec(select(Yield).where(Yield.state == state)).all()
                counties = sorted({y.county for y in yield_rows})

        if not counties:
            logger.error("No counties found for state=%s — run the full ingest first.", state)
            return

        logger.info("Fetching Daymet daily weather for %d counties in %s (%d–%d)…",
                    len(counties), state, start_year, end_year)

        for i, county in enumerate(counties, 1):
            logger.info("[%d/%d] %s, %s", i, len(counties), county, state)
            try:
                _annual_df, daily_df = fetch_and_transform_weather(county, state, start_year, end_year)
                if daily_df is not None and not daily_df.empty:
                    n = save_daily_weather_to_db(daily_df, state)
                    logger.info("  → %d rows saved", n)
            except Exception as exc:
                logger.error("  → failed for %s: %s", county, exc)

        logger.info("Daily weather ingest complete for %s.", state)
    finally:
        with _daily_weather_lock:
            _daily_weather_running = False


@router.post("/trigger", response_model=Message)
async def trigger_ingestion(background_tasks: BackgroundTasks) -> Message:
    """Legacy: trigger the full bulk ingestion pipeline."""
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
    """Legacy: fetch Daymet daily weather for every county in *state*."""
    global _daily_weather_running
    with _daily_weather_lock:
        if _daily_weather_running:
            raise HTTPException(status_code=409, detail="Daily weather ingest is already running.")
        _daily_weather_running = True
    background_tasks.add_task(_run_daily_weather_ingest, req.state, req.start_year, req.end_year)
    return Message(
        message=f"Daily weather ingest started for {req.state} ({req.start_year}–{req.end_year})."
    )


@router.get("/status", response_model=IngestStatus)
async def get_ingest_status() -> IngestStatus:
    """Legacy: return whether the full ingestion pipeline is currently running."""
    return IngestStatus(status="running" if _ingest_running else "idle")
