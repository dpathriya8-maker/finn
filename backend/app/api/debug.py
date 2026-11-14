"""TEMPORARY admin-only route: which data sources are reachable from the machine this runs on.

Step 3 uses it once on Render to fill the 'Render' column of docs/data-sources.md. Remove it
(and `probes/`) from the deployed app once that table is filled in.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_admin, validate_ticker
from probes.probes import report

router = APIRouter(prefix="/debug", dependencies=[Depends(require_admin)], include_in_schema=False)


@router.get("/sources")
def sources(symbol: str = "RELIANCE") -> dict:
    """Runs each source probe with a tiny payload. Needs the X-Admin-Token header."""
    return report(validate_ticker(symbol))
