"""Part B scenarios: follow companies, people and topics (filings only). Registered from live_scenarios.define."""
import json

SEVEN = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:168})); true"
INTERESTED = "document.getElementById('tab-interested').click()"
FEED = "document.querySelector('[data-testid=following-feed]')"
BOX = "document.querySelector('input[placeholder=\"Follow a company, person or topic\"]')"


def follow(**kw) -> str:
    """Put what the reader follows (companies, people, topics) into storage before the page is opened."""
    full = {"companies": [], "people": [], "topics": [], **kw}
    return f"localStorage.setItem('finn.follow.v1', {json.dumps(json.dumps(full))}); true"


def type_and(text: str, then: str) -> str:
    """Type into the search box, wait, then evaluate `then` (an expression that may use the suggestions)."""
    return f"(() => {{ window.__setVal({BOX}, {json.dumps(text)}); return new Promise(r => setTimeout(() => r({then}), 350)); }})()"


def define(scenario) -> None:
    scenario(
        "follow-empty",
        "/",
        setup=[SEVEN],
        steps=[INTERESTED],
        wait=5,
        shot_name="follow-empty",
        checks=[
            ("one search box with the right words", f"!!{BOX}"),
            ("ten starter topics", "document.querySelectorAll('[aria-label=\"Topics to follow\"] button').length === 10"),
            ("no feed until something is followed", f"!{FEED}"),
            (
                "the honest note names the number of companies",
                "/FINN follows filings from the 22 companies it tracks\\. Any NSE company is next\\./.test(document.querySelector('[data-testid=follow-note]').textContent)",
            ),
            ("no Preview badge on following", "![...document.querySelectorAll('#panel-interested span')].some(e => e.textContent.trim() === 'Preview')"),
            ("the word news is never used", "!/\\bnews\\b/i.test(document.getElementById('panel-interested').textContent)"),
        ],
    )
    scenario(
        "follow-topic",
        "/",
        setup=[SEVEN, follow(topics=["results"])],
        steps=[INTERESTED],
        wait=5,
        shot_name="follow-topic",
        expand=True,
        checks=[
            (
                "the feed shows Kaynes results with a grey 'Because you follow Results'",
                f"{FEED}.textContent.includes('Kaynes') && [...{FEED}.querySelectorAll('[data-testid=because]')].some(e => e.textContent === 'Because you follow Results')",
            ),
            ("a research company's results (HAL) is there too", f"{FEED}.textContent.includes('Hindustan Aeronautics') || {FEED}.textContent.includes('HAL')"),
            ("a chip with a way to stop", "!!document.querySelector('button[aria-label=\"Stop following Results\"]')"),
            ("the risk (Kaynes profit down) is the first card", f"{FEED}.querySelector('article').textContent.includes('Kaynes')"),
        ],
    )
    scenario(
        "follow-company-and-topic",
        "/",
        setup=[SEVEN, follow(companies=["KAYNES", "BAJFINANCE"], topics=["results"])],
        steps=[INTERESTED],
        wait=5,
        checks=[
            (
                "a filing that matches a company and a topic appears once, with both reasons",
                f"[...{FEED}.querySelectorAll('[data-testid=because]')].filter(e => e.textContent === 'Because you follow Kaynes Technology India, Results').length === 1",
            ),
            ("a research company (Bajaj Finance) is followed by symbol", f"{FEED}.textContent.includes('Bajaj')"),
            (
                "no filing is listed twice",
                f"(() => {{ const h = [...{FEED}.querySelectorAll('article button > span:first-child')].map(e => e.textContent); return h.length > 0 && h.length === new Set(h).size; }})()",
            ),
        ],
    )
    scenario(
        "follow-person",
        "/",
        setup=[SEVEN, follow(people=["V. Srinivasa Rangan"])],
        steps=[INTERESTED],
        wait=5,
        checks=[
            (
                "a filing naming them shows, from HDFC Bank, with the reason",
                f"{FEED}.textContent.includes('HDFC') && [...{FEED}.querySelectorAll('[data-testid=because]')].some(e => e.textContent === 'Because you follow V. Srinivasa Rangan')",
            ),
            ("it is matched by exact name only: no other company appears", f"[...{FEED}.querySelectorAll('article')].every(a => a.textContent.includes('HDFC'))"),
        ],
    )
    scenario(
        "follow-nothing-found",
        "/",
        setup=[SEVEN, follow(people=["Zed Nonexistent"], topics=["pledging"])],
        steps=[INTERESTED],
        wait=5,
        checks=[
            (
                "an honest line for each followed thing with no filings",
                "(() => { const t = document.querySelector('[data-testid=nothing-lines]').textContent; return t.includes('No filings about Zed Nonexistent in the last 7 days.') && t.includes('No filings about Pledging in the last 7 days.'); })()",
            ),
            ("it says 0 filings", f"{FEED}.textContent.includes('0 filings')"),
        ],
    )
    scenario(
        "follow-search",
        "/",
        setup=[SEVEN],
        steps=[INTERESTED],
        wait=5,
        checks=[
            (
                "typing 'kay' offers Kaynes; tapping follows it and shows a chip",
                f"(() => {{ window.__setVal({BOX}, 'kay'); return new Promise(r => setTimeout(() => {{ const b = window.__byText('[data-testid=suggestions] button', 'Kaynes'); if (!b) return r(false); b.click(); setTimeout(() => r(JSON.parse(localStorage.getItem('finn.follow.v1')).companies.includes('KAYNES') && !!document.querySelector('button[aria-label^=\"Stop following Kaynes\"]')), 300); }}, 350)); }})()",
            ),
            ("a research company is found by name (Bajaj)", type_and("bajaj", "!!window.__byText('[data-testid=suggestions] button', 'Bajaj Finance')")),
            (
                "a person's full name can be followed even if not listed",
                f"(() => {{ window.__setVal({BOX}, 'Ravi Kumar'); return new Promise(r => setTimeout(() => {{ const b = window.__byText('[data-testid=suggestions] button', 'Ravi Kumar'); if (!b) return r(false); b.click(); setTimeout(() => r(JSON.parse(localStorage.getItem('finn.follow.v1')).people.includes('Ravi Kumar')), 300); }}, 350)); }})()",
            ),
            ("something FINN does not track says so, honestly", type_and("zzzz", "document.querySelector('[data-testid=suggestions]').textContent.includes('Any NSE company is next')")),
            (
                "tapping the x stops following",
                "(() => { document.querySelector('button[aria-label=\"Stop following Kaynes Technology India\"]').click(); return new Promise(r => setTimeout(() => r(!JSON.parse(localStorage.getItem('finn.follow.v1')).companies.includes('KAYNES')), 300)); })()",
            ),
        ],
    )
    scenario(
        "follow-orders",
        "/",
        setup=[SEVEN, follow(topics=["orders"])],
        steps=[INTERESTED],
        wait=5,
        checks=[("the order win filed as an update is found by its words", f"{FEED}.textContent.includes('Larsen')")],
    )
