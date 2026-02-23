from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models import Message

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/trigger", response_model=Message)
async def trigger_ingestion(background_tasks: BackgroundTasks) -> Message:
    """
    Trigger the bulk data ingestion pipeline in the background.
    Uses the CSV fallback if no NASS_API_KEY is set.
    """
    try:
        from app.ingest.runner import main as run_ingestion
        background_tasks.add_task(run_ingestion)
        return Message(message="Data ingestion started in background.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
