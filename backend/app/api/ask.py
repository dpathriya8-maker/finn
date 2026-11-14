"""Ask-the-documents route: answers only from the ingested filings.

POST /ask {"ticker": "...", "question": "..."} returns one of three outcomes, always named in `status`:
answered (with quotes), passages (the closest passages, when no model could answer) or not_found.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter

from app.api.research import NO_STORE, get_engine
from app.core.security import validate_ticker
from app.pull.ask import BadQuestion
from app.pull.engine import NeedResearch
from app.pull.ingest import NoDocuments


class AskBody(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    question: str = Field(min_length=1, max_length=2000)  # the real limit (300 characters) is applied, with a clear message, by the engine


def build_router(limiter: Limiter, global_limit: str) -> APIRouter:
    router = APIRouter(tags=["ask"])

    @router.post("/ask")
    @limiter.limit("10/minute")
    @limiter.shared_limit(global_limit, scope="global")
    def ask(request: Request, body: AskBody) -> JSONResponse:
        symbol = validate_ticker(body.ticker)
        try:
            return JSONResponse(get_engine(request).ask(symbol, body.question), headers=NO_STORE)
        except BadQuestion as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422, headers=NO_STORE)
        except NeedResearch as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409, headers=NO_STORE)
        except NoDocuments as exc:
            return JSONResponse({"detail": exc.reason}, status_code=404, headers=NO_STORE)
        except Exception:  # never a stack trace to a browser
            return JSONResponse({"detail": "The documents could not be searched just now. Try again in a moment."}, status_code=502, headers=NO_STORE)

    return router
