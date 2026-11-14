"""The 17 announcement categories, read once from config/categories.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from app.core.settings import REPO_ROOT


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    why: str  # short line shown on a card to explain its rank
    weight: int  # base priority 0-100
    is_routine: bool
    default_alert: bool
    card_type: str  # results | management | one_liner | surface_only


@lru_cache(maxsize=1)
def load() -> dict[str, Category]:
    raw = json.loads((REPO_ROOT / "config" / "categories.json").read_text(encoding="utf-8"))["categories"]
    return {
        c["id"]: Category(
            id=c["id"],
            label=c["label"],
            why=c["why"],
            weight=int(c["weight"]),
            is_routine=bool(c["is_routine"]),
            default_alert=bool(c["default_alert"]),
            card_type=c["card_type"],
        )
        for c in raw
    }
