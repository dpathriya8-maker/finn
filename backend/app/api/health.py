"""GET /health route."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.settings import VERSION
from app.core.timeutil import now_ist

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check used by Render and by the frontend status pill."""
    return {
        "status": "ok",
        "version": VERSION,
        "time_ist": now_ist().isoformat(timespec="seconds"),
    }
