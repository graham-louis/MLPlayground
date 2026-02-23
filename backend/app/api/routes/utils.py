from fastapi import APIRouter
from app.models import Message

router = APIRouter(prefix="/utils", tags=["utils"])


@router.get("/health-check/", response_model=Message)
async def health_check() -> Message:
    return Message(message="OK")
