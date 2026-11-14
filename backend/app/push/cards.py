"""Cards that need a look inside the filing: the figures of a results filing, and who is involved in a management
change. Anything that goes wrong becomes a card that says so, because a missing card with no explanation reads as a bug.

This never raises: one unreadable filing must not take the company's other data, or the run, down with it.
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.cache import Cache, digest_key
from app.push import digest
from app.push import mgmt_card as mc
from app.push import results_card as rc

MAX_PER_COMPANY = 2  # results filings read per company and run: a quarter has one, the rest is noise
MAX_MANAGEMENT_PER_COMPANY = 3
PRIORITY_BUMP = {"bad": 7, "watch": 3}  # negativity bias: weaker numbers rank above equally "material" good news
RANK_NOTE = {
    "bad": "Weaker than a year ago, so it ranks higher",
    "watch": "Softer than a year ago, so it ranks a little higher",
}


class PdfOnce:
    """Wraps the downloader for one company's run: the same URL is fetched once. A board-outcome letter that holds
    the results and a director's retirement is one 9 MB file, filed under two announcements."""

    def __init__(self, fetch: Callable[[str], bytes]):
        self.fetch, self.kept = fetch, {}

    def __call__(self, url: str) -> bytes:
        if url not in self.kept:
            self.kept[url] = self.fetch(url)
        return self.kept[url]


def _failed_download(exc: Exception, kind: str) -> dict[str, Any]:
    reason = f"The filing could not be downloaded just now ({type(exc).__name__}). Open it from the link."
    return {"type": kind, "status": "failed", "reason": reason, "extractor": rc.EXTRACTOR_VERSION if kind == "results" else mc.EXTRACTOR_VERSION}


# ------------------------------------------------------------------------------------------------ results
def cache_key(url: str) -> str:
    return f"results:v{rc.EXTRACTOR_VERSION}:{url}"


def headline_for(card: dict[str, Any]) -> str | None:
    """"Q2 FY27 results: profit down 31% from a year ago; revenue up 4%", built from the card's computed figures."""
    reason = card.get("tone_reason")
    if not reason:
        return None
    label = card["period"]["label"]
    lead = "Results" if label == "Latest quarter" else f"{label} results"
    return f"{lead}: {reason[0].lower()}{reason[1:]}"


def apply_card(item: dict[str, Any], card: dict[str, Any]) -> None:
    """Attach the card and let its numbers decide the item's tone, rank and headline."""
    item["card"] = card
    if card.get("status") not in ("ok", "partial"):
        return
    tone = card["tone"]
    item["tone"] = tone
    item["priority"] = min(100, item["priority"] + PRIORITY_BUMP.get(tone, 0))
    if tone in RANK_NOTE:
        item["why"] = f"{RANK_NOTE[tone]}. {item['why']}"
    headline = headline_for(card)
    if headline:
        item["headline"] = headline


def _reading(url: str, pdf: Callable[[str], bytes], cache: Cache | None) -> tuple[dict[str, Any], bool]:
    """What the filing says, from the cache or else from the downloaded PDF. Returns (reading, was_cached).
    A download that fails raises; a PDF that cannot be read is a reading like any other and is stored."""
    key = cache_key(url)
    if cache is not None:
        stored = cache.get(key)
        if isinstance(stored, dict):
            return stored, True
    reading = rc.read_pdf(pdf(url))
    if cache is not None:
        cache.set(key, reading)
    return reading, False


def attach_results_cards(
    items: list[dict[str, Any]],
    *,
    yahoo: list[dict[str, Any]],
    pdf: Callable[[str], bytes],
    cache: Cache | None = None,
    previous: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Give the newest results filings of ONE company a card. `previous` maps item id to the card of the last run:
    if the download fails now, a good card from before is kept instead of replacing it with an error.
    Returns counts for the run log."""
    counts = {"ok": 0, "partial": 0, "failed": 0, "cached": 0, "reused": 0}
    wanted = sorted(
        (i for i in items if i.get("card_type") == "results" and i.get("url") and "card" not in i),
        key=lambda i: i["published_at"],
        reverse=True,
    )
    for item in wanted[:MAX_PER_COMPANY]:
        try:
            reading, was_cached = _reading(item["url"], pdf, cache)
        except Exception as exc:  # the download failed: blocked, too large, not a PDF, network
            earlier = (previous or {}).get(item["id"])
            if earlier and earlier.get("type") == "results" and earlier.get("status") in ("ok", "partial"):
                apply_card(item, earlier)
                counts["reused"] += 1
                continue
            apply_card(item, _failed_download(exc, "results"))
            counts["failed"] += 1
            continue
        card = rc.card_from_reading(reading, hint_text=f"{item.get('subject', '')} {item.get('body', '')}", yahoo=yahoo, source_url=item["url"])
        apply_card(item, card)
        counts[card["status"]] += 1
        counts["cached"] += was_cached
    return counts


# ------------------------------------------------------------------------------------------------ management
def management_key(item: dict[str, Any]) -> str:
    """The reading depends on the file and on the headline (a filing can announce several things)."""
    return f"mgmt:v{mc.EXTRACTOR_VERSION}:{digest_key(item['url'], item['headline'])}"


def _facts_text(card: dict[str, Any]) -> str:
    """The card's facts as the words the classifier's rules already understand: "cessation of Dr. X as Chief Executive Officer"."""
    return " ".join(f"{p['kind']} of {p['name']} as {p['role']}." for p in card["people"])


def apply_management_card(item: dict[str, Any], card: dict[str, Any]) -> None:
    """Attach the card. Its facts can sharpen the headline, and they take part in ranking, so a key person leaving
    outranks a hire even when the announcement's own headline was vague ("Change in Management")."""
    item["card"] = card
    if card.get("status") != "ok":
        return
    person = card["people"][0]
    surname = person["name"].split()[-1].lower().strip(".")
    if item["headline"].endswith(("…", "...")) or surname not in item["headline"].lower():
        headline = mc.headline_for(card)
        if headline:
            item["headline"] = headline
    update = digest.reclassify(item, _facts_text(card))
    if update and update["priority"] >= item["priority"]:  # facts may raise a filing's rank, never lower it
        item.update(update)


def attach_management_cards(
    items: list[dict[str, Any]],
    *,
    pdf: Callable[[str], bytes],
    cache: Cache | None = None,
    previous: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    counts = {"ok": 0, "partial": 0, "failed": 0, "cached": 0, "reused": 0}
    wanted = sorted(
        (i for i in items if i.get("card_type") == "management" and i.get("url") and "card" not in i),
        key=lambda i: i["published_at"],
        reverse=True,
    )
    for item in wanted[:MAX_MANAGEMENT_PER_COMPANY]:
        key, reading, was_cached = management_key(item), None, False
        stored = cache.get(key) if cache is not None else None
        try:
            if isinstance(stored, dict) and isinstance(stored.get("card"), dict):
                reading, was_cached = stored, True
            else:
                reading = mc.read_filing(pdf(item["url"]), item["headline"], item.get("subject", ""), item.get("company", ""))
                if cache is not None:
                    cache.set(key, reading)
        except Exception as exc:  # the download failed
            earlier = (previous or {}).get(item["id"])
            if earlier and earlier.get("type") == "management" and earlier.get("status") in ("ok", "partial"):
                apply_management_card(item, earlier)
                counts["reused"] += 1
                continue
            apply_management_card(item, _failed_download(exc, "management"))
            counts["failed"] += 1
            continue
        card = {**reading["card"], "source": {**reading["card"].get("source", {}), "url": item["url"]}} if reading["card"].get("status") != "failed" else reading["card"]
        apply_management_card(item, card)
        counts[card["status"]] += 1
        counts["cached"] += was_cached
    return counts
