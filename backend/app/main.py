"""FastAPI app entrypoint: CORS, per-IP rate limiting and router wiring."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import health
from app.core.security import build_limiter
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FINN API", version=settings.version)

    limiter = build_limiter(settings.rate_limit_default)
    limiter.exempt(health.health)  # Render's health check must never be throttled
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware added last runs first. CORS goes on the outside so that even a 429 carries
    # CORS headers; otherwise the browser would report a CORS error instead of "too many requests".
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
        allow_credentials=False,
    )

    app.include_router(health.router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "finn-api", "version": settings.version}

    return app


app = create_app()
