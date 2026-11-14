"""PULL research routes: Promise Tracker for any NSE ticker.

GET  /research/{ticker}  the finished record (200), a job in progress with its stage (202), a failed one with its reason
                         (200, state "failed"), or nothing yet (404).
POST /research/{ticker}  start fresh research if none exists: 202 while it runs, 200 if a record already exists, 429 once
                         the day's allowance of fresh research is used. Cached research is never refused.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter

from app.core.security import validate_ticker
from app.pull.engine import CapReached, Engine

NO_STORE = {"Cache-Control": "no-store"}


def get_engine(request: Request) -> Engine:
    """One engine per app, built on first use so that importing the app (and its tests) does not open a database."""
    state = request.app.state
    if getattr(state, "engine", None) is None:
        state.engine = Engine.from_env()
    return state.engine


def respond(result: dict) -> JSONResponse:
    code = {"ready": 200, "running": 202, "failed": 200, "none": 404}[result["state"]]
    return JSONResponse(result, status_code=code, headers=NO_STORE)


def build_router(limiter: Limiter, global_limit: str) -> APIRouter:
    router = APIRouter(tags=["research"])

    @router.get("/research/{ticker}")
    @limiter.limit("60/minute")
    @limiter.shared_limit(global_limit, scope="global")  # one allowance per address across every route that carries it
    def read_research(request: Request, ticker: str) -> JSONResponse:
        return respond(get_engine(request).state(validate_ticker(ticker)))

    @router.post("/research/{ticker}")
    @limiter.limit("6/minute")
    @limiter.shared_limit(global_limit, scope="global")
    def start_research(request: Request, ticker: str) -> JSONResponse:
        symbol = validate_ticker(ticker)
        try:
            return respond(get_engine(request).start(symbol))
        except CapReached as exc:
            detail = "Today's allowance of fresh research has been used. Research already done is unaffected; try again tomorrow."
            return JSONResponse({"detail": detail, "cap": exc.cap}, status_code=429, headers=NO_STORE)

    return router
