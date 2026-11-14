"""India Standard Time helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# India has no daylight saving, so a fixed offset is exact and needs no tz database.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_ist() -> datetime:
    return datetime.now(IST)


def parse_ist(text: str, fmt: str | None = None) -> datetime:
    """Parse a timestamp the exchanges publish in local time (no zone) and mark it as IST."""
    parsed = datetime.strptime(text, fmt) if fmt else datetime.fromisoformat(text)
    return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed.astimezone(IST)
