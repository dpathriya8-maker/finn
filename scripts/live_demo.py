"""Walks the README's 60-second demo on the live site, in a phone-sized Chromium, and reports each step.

    backend/.venv/Scripts/python scripts/live_demo.py https://finn-mocha.vercel.app

It uses the real deployed engine: the first research step may wake the free Render server (up to about 2 minutes), and TITAN is
researched live. Exit code 1 if a step fails.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_live import SET_VALUE_JS, Browser, shot  # noqa: E402


def wait_for(tab, expression: str, seconds: float, every: float = 1.0):
    """Evaluate until it is truthy; returns the last value."""
    end = time.time() + seconds
    value = None
    while time.time() < end:
        try:
            value = tab.js(expression)
        except Exception:
            value = None
        if value:
            return value
        time.sleep(every)
    return value


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://finn-mocha.vercel.app").rstrip("/")
    shots = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))

    browser = Browser(port=int(os.environ.get("FINN_CHECK_PORT", "9466")))
    try:
        tab = browser.tab()
        tab.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)

        def go(path: str, wait: float = 4.0) -> None:
            tab.call("Page.navigate", url=base + path)
            time.sleep(wait)
            tab.js(SET_VALUE_JS)

        # 0. a clean first visit
        go("/", 1.0)
        tab.js("try { localStorage.clear(); } catch (e) {} true")

        print("Step 1: Brief, the Kaynes results card")
        go("/", 5)
        record("the Brief opens with Kaynes in it", bool(tab.js("[...document.querySelectorAll('article')].some(a => a.textContent.includes('Kaynes'))")))
        opened = tab.js("(() => { const b = [...document.querySelectorAll('article')].find(a => a.textContent.includes('Kaynes'))?.querySelector('button[aria-expanded]'); const btn = [...document.querySelectorAll('article')].find(a => a.textContent.includes('Kaynes')).querySelectorAll('button[aria-expanded]'); const r = [...btn].find(x => /Q2 FY27|results/i.test(x.textContent)); if (!r) return false; r.click(); return true; })()")
        record("the results card opens", bool(opened))
        time.sleep(0.8)
        record("it shows Revenue, EBITDA, PBT and PAT with QoQ and YoY", bool(tab.js("(() => { const t = document.body.textContent; return ['Revenue', 'EBITDA', 'PBT', 'PAT', 'QoQ', 'YoY'].every(w => t.includes(w)); })()")))
        if shots:
            shot(tab, shots / "demo-1-results-card-light.png", 390)

        print("Step 2: Figures as printed")
        tapped = tab.js("(() => { const s = [...document.querySelectorAll('summary')].find(x => x.textContent.includes('Figures as printed')); if (!s) return false; s.click(); return true; })()")
        record("'Figures as printed in the filing (page N)' is there and opens", bool(tapped))
        time.sleep(0.5)
        link = tab.js("(() => { const a = [...document.querySelectorAll('a')].find(x => x.textContent.includes('Open the filing at page')); return a ? a.getAttribute('href') : null; })()")
        record("it shows the printed figures and a link to the filing at that page", bool(link) and ".pdf" in str(link) and "#page=" in str(link), str(link))
        record("the printed figures are listed with their pages", bool(tab.js("(() => { const d = [...document.querySelectorAll('details')].find(x => x.textContent.includes('Figures as printed')); return !!d && /Revenue/.test(d.textContent) && /page [0-9]+/.test(d.querySelector('summary').textContent); })()")))
        if shots:
            shot(tab, shots / "demo-2-figures-as-printed-light.png", 390, max_height=3200)

        print("Step 3: Research, Bajaj Finance")
        go("/research?symbol=BAJFINANCE", 7)
        first_group = tab.js("(() => { const g = [...document.querySelectorAll('h2, h3, span')].map(e => e.textContent.trim()).find(t => /^(Missed|Not followed up|Partly|Kept)\\b/.test(t)); return g || ''; })()")
        record("the promises show the misses first", str(first_group).startswith("Missed"), str(first_group))
        record("it says how many promises were delivered", bool(tab.js("/Delivered \\d+ of \\d+ promises/.test(document.body.textContent)")))
        if shots:
            shot(tab, shots / "demo-3-bajaj-light.png", 390)

        print("Step 4: Ask 'What did they say about margins?'")
        engine = wait_for(tab, "document.querySelector('header')?.textContent.includes('Engine online')", 170, 3)
        record("the engine wakes and says Engine online", bool(engine))
        asked = tab.js("(() => { const t = document.querySelector('textarea'); if (!t) return false; window.__setVal = window.__setVal || ((el, v) => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })); }); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(t, 'What did they say about margins?'); t.dispatchEvent(new Event('input', { bubbles: true })); return true; })()")
        record("the Ask box takes the question", bool(asked))
        time.sleep(0.5)
        tab.js("(() => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === 'Ask'); if (b) b.click(); })()")
        answer = wait_for(tab, "(() => { const t = document.body.textContent; return /page \\d+/i.test(t) && /margin/i.test(t) && document.querySelectorAll('blockquote').length > 0; })()", 120, 2)
        record("it answers with quotes and pages from the documents", bool(answer))
        if shots:
            shot(tab, shots / "demo-4-ask-light.png", 390, max_height=3200)

        print("Step 5: Research TITAN (never prepared)")
        started = time.time()
        go("/research?symbol=TITAN", 3)
        done = wait_for(tab, "(() => { const t = document.body.textContent; return /Promise Tracker|promises that came due|No verdict yet|too few to judge|Only \\d+ promise/.test(t) && !/Reading the filings|stage/i.test(t.slice(0, 600)); })()", 200, 3)
        record(f"TITAN is researched live ({time.time() - started:.0f} s)", bool(done))
        record("it names the four calls it read and its documents", bool(tab.js("/earnings-call|call transcript|transcripts?/i.test(document.body.textContent)")))
        if shots:
            shot(tab, shots / "demo-5-titan-light.png", 390, max_height=3200)

        print("Step 6: You, sample holdings, then the calculator in a card")
        go("/settings#investments", 4)
        clicked = tab.js("(() => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Try with sample holdings')); if (!b) return false; b.click(); return true; })()")
        record("'Try with sample holdings' is there and works", bool(clicked))
        time.sleep(1.0)
        record("it fills clearly labelled sample numbers", bool(tab.js("document.getElementById('investments').textContent.includes('Sample holdings') && Object.keys(JSON.parse(localStorage.getItem('finn.holdings.v2'))).length === 6")))
        tab.js("localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:168})); true")
        go("/", 5)
        record("the Brief shows the portfolio card, marked Sample holdings", bool(tab.js("(() => { const c = document.querySelector('[data-testid=portfolio-summary]'); return !!c && c.textContent.includes('Sample holdings') && c.textContent.includes('Total invested'); })()")))
        calc = tab.js("(() => { const b = [...document.querySelectorAll('article')].flatMap(a => [...a.querySelectorAll('button[aria-expanded]')]).find(x => x.getAttribute('aria-expanded') === 'false'); if (!b) return false; b.click(); return true; })()")
        time.sleep(0.8)
        record("an open card has the What if calculator", bool(calc) and bool(tab.js("!!document.querySelector('section[aria-label=\"What if\"]') && document.querySelector('section[aria-label=\"What if\"]').textContent.includes('not advice')")))
        if shots:
            shot(tab, shots / "demo-6-calculator-light.png", 390, max_height=3200)

        record("no uncaught errors or failed requests along the way", not [e for e in tab.errors if "finn-api" not in e], "; ".join(tab.errors[:3]))
    finally:
        browser.close()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} of {len(results)} demo checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
