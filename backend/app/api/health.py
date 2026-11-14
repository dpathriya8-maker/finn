"""GET /health route."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.core.settings import VERSION

router = APIRouter()

# India has no daylight saving, so a fixed offset is exact and needs no tz database.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check used by Render and by the frontend status pill."""
    return {
        "status": "ok",
        "version": VERSION,
        "time_ist": datetime.now(IST).isoformat(timespec="seconds"),
    }
