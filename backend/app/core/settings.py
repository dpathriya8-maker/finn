"""Environment-driven settings (keys, model names, caps); nothing hard-coded."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

VERSION = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parents[3]
# Local development reads <repo>/.env. On Render the platform injects real environment
# variables, and load_dotenv never overrides a variable that is already set.
load_dotenv(REPO_ROOT / ".env", override=False)

# The browser origins that may always call the API during development.
LOCAL_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def parse_origins(value: str | None) -> list[str]:
    """ALLOWED_ORIGINS plus localhost. Never a wildcard; trailing slashes are removed."""
    origins = [o.rstrip("/") for o in _csv(value) if o != "*"]
    for local in LOCAL_ORIGINS:
        if local not in origins:
            origins.append(local)
    return origins


@dataclass(frozen=True)
class Settings:
    version: str
    allowed_origins: list[str]
    rate_limit_default: str
    admin_token: str | None


def get_settings() -> Settings:
    """Read settings fresh from the environment so tests can change them."""
    return Settings(
        version=VERSION,
        allowed_origins=parse_origins(os.getenv("ALLOWED_ORIGINS")),
        rate_limit_default=os.getenv("RATE_LIMIT_DEFAULT", "30/minute"),
        admin_token=os.getenv("ADMIN_TOKEN") or None,
    )
