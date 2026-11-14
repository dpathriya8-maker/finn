"""Priority score per filing, with a human-readable reason for why it ranked high."""
from __future__ import annotations

from dataclasses import dataclass

from app.push.categories import load as categories
from app.push.classify import Classification


@dataclass(frozen=True)
class Scored:
    category: str
    label: str
    priority: int  # 0-100, higher is shown first
    routine: bool  # collapsed into the "N routine filings" row
    why: str  # one line explaining the rank, shown on the card
    default_alert: bool
    card_type: str


def score(c: Classification) -> Scored:
    """Base weight of the category plus the rule's adjustment, clamped to 0-100.

    The weights already put risks above good news (litigation 95, pledging 90 against dividends 50), and
    the adjustments carry that into the filing: a downgrade goes up, a reaffirmation goes down.
    """
    cat = categories()[c.category]
    priority = max(0, min(100, cat.weight + c.adjust))
    routine = c.routine or cat.is_routine
    if routine:
        why = cat.why if cat.is_routine and not c.note else f"Routine: {c.note or cat.why}"
    else:
        why = f"{c.note}. {cat.why}" if c.note else cat.why
    return Scored(cat.id, cat.label, priority, routine, why, cat.default_alert, cat.card_type)
