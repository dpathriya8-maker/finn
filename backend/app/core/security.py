"""Rate limiting, ticker validation and the admin-token check."""
from __future__ import annotations

import re
import secrets

from fastapi import Header, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.settings import get_settings

# NSE symbols: capitals, digits, & and -. Anything else is rejected before it reaches a source.
TICKER_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")


def build_limiter(default_limit: str) -> Limiter:
    """Per-IP limiter held in memory (one Render instance, so no shared store is needed).

    Limits are counted per ENDPOINT, not per URL. slowapi's default is the URL, which would give every ticker its own
    counter on /research/{ticker}, so a client could dodge "6 fresh researches a minute" by asking for a different ticker
    each time.

    NOTE: the default limit is applied by slowapi's middleware, and with this FastAPI the middleware cannot see routes that
    were added with include_router, so it does not reach them. Routes in a router therefore state their own limits with
    @limiter.limit and the shared global one with @limiter.shared_limit (see app/api/research.py)."""
    return Limiter(key_func=get_remote_address, default_limits=[default_limit], key_style="endpoint")


def validate_ticker(value: str) -> str:
    """Return the ticker upper-cased and trimmed, or raise 422 if it is not a valid NSE symbol."""
    ticker = value.strip().upper()
    if not TICKER_RE.fullmatch(ticker):
        raise HTTPException(status_code=422, detail="Invalid ticker")
    return ticker


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Dependency for debug and admin routes. Closed when ADMIN_TOKEN is not configured."""
    expected = get_settings().admin_token
    if not expected or not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
