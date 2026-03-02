"""
Ingestion orchestration endpoints for MLPlayground.

Provides:
  POST /api/v1/ingest/run          — trigger ingest for any registered datasource
  GET  /api/v1/ingest/status/{id}  — poll job progress
"""
import logging
import threading
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.db_models import Message

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory job store (process-local; suitable for single-worker deployments)
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


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


# ---------------------------------------------------------------------------
# Generic run / status
# ---------------------------------------------------------------------------

def _run_generic_ingest(job_id: str, sources: list[str], scope: dict) -> None:
    """
    Background worker: calls each registered datasource plugin's fetch + upsert.

    Uses inspect.signature() to detect which kwargs each fetch() accepts and
    routes accordingly — no hardcoded county/state/year assumptions.
    """
    import inspect
    from app.ingest.registry import DATASOURCE_REGISTRY
    from app.ingest._daymet_helpers import get_counties_for_state

    errors: list[str] = []
    total_steps = max(len(sources), 1)
    step = 0

    def _update(status: str, msg: str, progress: float) -> None:
        with _jobs_lock:
            _jobs[job_id].update(status=status, message=msg, progress=progress, errors=errors)

    _update("running", "Starting…", 0.0)

    # Normalise "states": may be a CSV string or already a list
    states: list[str] = scope.get("states", ["North Carolina"])
    if isinstance(states, str):
        states = [s.strip() for s in states.split(",") if s.strip()]

    for source_key in sources:
        entry = DATASOURCE_REGISTRY.get(source_key)
        if entry is None:
            errors.append(f"Unknown datasource key: {source_key!r}")
            step += 1
            _update("running", f"Skipped unknown source '{source_key}'", step / total_steps)
            continue

        if entry.fetch_fn is None or entry.upsert_fn is None:
            errors.append(f"{source_key}: missing fetch_fn or upsert_fn — cannot ingest.")
            step += 1
            continue

        # Introspect which kwargs fetch() accepts
        sig = inspect.signature(entry.fetch_fn)
        accepted = set(sig.parameters.keys()) - {"self"}
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )

        def _build_kwargs(extra: dict) -> dict:
            """Merge scope + extra, then filter to accepted kwargs (with type coercion)."""
            merged = {**scope, **extra}
            result: dict = {}
            for k, v in merged.items():
                if k == "states":          # never forward the batch list
                    continue
                if not has_var_keyword and k not in accepted:
                    continue
                param = sig.parameters.get(k)
                if param is not None:
                    ann = param.annotation
                    if ann not in (inspect.Parameter.empty, type(None)) and ann in (int, float, str):
                        try:
                            v = ann(v)
                        except (ValueError, TypeError):
                            pass
                result[k] = v
            return result

        # Route by signature shape
        if "county" in accepted or has_var_keyword:
            for state in states:
                counties = get_counties_for_state(state)
                county_total = max(len(counties), 1)
                for c_idx, county in enumerate(counties, 1):
                    kwargs = _build_kwargs({"county": county, "state": state})
                    label = f"{county}, {state}"
                    try:
                        df = entry.fetch_fn(**kwargs)
                        entry.upsert_fn(df)
                    except Exception as exc:
                        errors.append(f"{source_key}/{label}: {exc}")
                        logger.error("Ingest error for %s/%s: %s", source_key, label, exc)
                    progress = (step + c_idx / county_total) / total_steps
                    _update("running", f"{source_key}: {label} ({c_idx}/{county_total})", progress)

        elif "state" in accepted:
            state_total = max(len(states), 1)
            for s_idx, state in enumerate(states, 1):
                kwargs = _build_kwargs({"state": state})
                try:
                    df = entry.fetch_fn(**kwargs)
                    entry.upsert_fn(df)
                except Exception as exc:
                    errors.append(f"{source_key}/{state}: {exc}")
                    logger.error("Ingest error for %s/%s: %s", source_key, state, exc)
                progress = (step + s_idx / state_total) / total_steps
                _update("running", f"{source_key}: {state} ({s_idx}/{state_total})", progress)

        else:
            # No geography parameter — single call
            kwargs = _build_kwargs({})
            try:
                df = entry.fetch_fn(**kwargs)
                entry.upsert_fn(df)
            except Exception as exc:
                errors.append(f"{source_key}: {exc}")
                logger.error("Ingest error for %s: %s", source_key, exc)

        step += 1
        _update("running", f"Completed {source_key}", step / total_steps)

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

