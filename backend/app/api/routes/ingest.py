import threading
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.models import Message

router = APIRouter(prefix="/ingest", tags=["ingest"])

_ingest_lock = threading.Lock()
_ingest_running = False


class IngestStatus(BaseModel):
    status: Literal["idle", "running"]


def _run_ingestion() -> None:
    global _ingest_running
    try:
        from app.ingest.runner import main as run_ingestion

        run_ingestion()
    finally:
        with _ingest_lock:
            _ingest_running = False


@router.post("/trigger", response_model=Message)
async def trigger_ingestion(background_tasks: BackgroundTasks) -> Message:
    """
    Trigger the bulk data ingestion pipeline in the background.
    Returns 409 if ingestion is already running.
    Uses the CSV fallback if no NASS_API_KEY is set.
    """
    global _ingest_running
    with _ingest_lock:
        if _ingest_running:
            raise HTTPException(status_code=409, detail="Ingestion is already running.")
        _ingest_running = True
    background_tasks.add_task(_run_ingestion)
    return Message(message="Data ingestion started in background.")


@router.get("/status", response_model=IngestStatus)
async def get_ingest_status() -> IngestStatus:
    """Return whether the ingestion pipeline is currently running."""
    return IngestStatus(status="running" if _ingest_running else "idle")
