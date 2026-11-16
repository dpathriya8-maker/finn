"""Part D scenarios: stale-data safety, the quiet-day window, the first-visit hint. Registered from live_scenarios.define."""
import json

SEVEN = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:168})); true"
TWENTY_FOUR = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:24})); true"
INTERESTED = "document.getElementById('tab-interested').click()"


def clock(iso: str) -> str:
    """Make the page believe the device's clock says `iso` (Date.now only: windows are never counted from it)."""
    return f"(() => {{ const at = Date.parse({json.dumps(iso)}); Date.now = () => at; }})();"


# Looks at the data itself: material filings (not routine, priority 45 or more) within a window counted from generated_at.
MATERIAL_IN = """
(async (hours, category) => {
  const b = await (await fetch('/data/brief.json')).json();
  const end = Date.parse(b.generated_at), start = end - hours * 3600000;
  return b.items.filter(i => { const t = Date.parse(i.published_at); return t >= start && t <= end + 60000 && (category ? i.category === category : (!i.routine && i.priority >= 45)); }).length;
})"""

FRESH = clock("2026-11-16T10:00:00+05:30")  # within a day of the data
STALE = clock("2026-11-26T10:00:00+05:30")  # ten days later


def define(scenario) -> None:
    scenario(
        "stale-brief",
        "/",
        init=[STALE],
        wait=5,
        shot_name="stale-brief",
        checks=[
            ("old data: the heading is 'Latest highlights'", "document.querySelector('h1').textContent.trim() === 'Latest highlights'"),
            (
                "the line reads 'Data as of <date, time>' and says it is the older data",
                "/^Data as of\\s\\d{1,2}\\s\\w{3},\\s\\d{1,2}:\\d{2}\\s(am|pm)\\sIST/.test(document.querySelector('[data-testid=data-as-of]').textContent.trim())",
            ),
            ("it also says what window is shown, from the data's time", "/Showing the last .* before then/.test(document.querySelector('h1').closest('section').textContent)"),
            ("the Brief is not empty ten days later", "!!document.querySelector('[data-testid=summary]') && document.querySelector('[data-testid=summary]').textContent.length > 0 && document.querySelectorAll('article').length > 0"),
            ("the footer does not say 'all caught up' or 'today' about old data", "document.querySelector('[data-testid=caught-up]').textContent.includes(\"That's everything in the latest data\") && !document.querySelector('[data-testid=caught-up]').textContent.includes('Today')"),
            ("the summary does not say it is a quiet day when filings exist", "!document.querySelector('[data-testid=summary]').textContent.startsWith('Quiet day') || document.querySelectorAll('article').length === 0"),
        ],
    )
    scenario(
        "stale-alerts",
        "/alerts",
        init=[STALE],
        wait=4,
        checks=[
            ("old data: Alerts says 'Latest alerts'", "document.querySelector('h1').textContent.trim() === 'Latest alerts'"),
            ("and 'Data as of'", "document.querySelector('[data-testid=data-as-of]').textContent.trim().startsWith('Data as of')"),
        ],
    )
    scenario(
        "fresh-brief",
        "/",
        init=[FRESH],
        wait=5,
        checks=[
            ("fresh data keeps the normal heading", "document.querySelector('h1').textContent.trim() !== 'Latest highlights'"),
            ("and the footer says all caught up", "document.querySelector('[data-testid=caught-up]').textContent.includes(\"You're all caught up\")"),
            ("and the data time is not in the warning colour", "!document.querySelector('[data-testid=data-as-of] p').className.includes('text-watch')"),
        ],
    )
    scenario(
        "fresh-alerts",
        "/alerts",
        init=[FRESH],
        wait=4,
        checks=[("fresh Alerts keeps its heading", "document.querySelector('h1').textContent.trim() === 'Alerts'")],
    )
    scenario(
        "quiet-day-looks-further-back",
        "/",
        init=[FRESH],
        wait=5,
        checks=[
            (
                "if nothing material in 24 hours, the Brief looks back and says so; if something is, it does not",
                f"(async () => {{ const m24 = await {MATERIAL_IN}(24); const note = document.querySelector('[data-testid=widened-note]'); const wider = (await {MATERIAL_IN}(72)) + (await {MATERIAL_IN}(168)); "
                "return m24 > 0 ? !note : (wider === 0 ? !note : (!!note && /Nothing material in the last 24 hours/.test(note.textContent) && document.querySelector('h1').textContent.trim() !== \"Today's Highlights\")); })()",
            ),
            (
                "it then shows material cards, not an empty day",
                f"(async () => {{ const any = (await {MATERIAL_IN}(24)) + (await {MATERIAL_IN}(72)) + (await {MATERIAL_IN}(168)); return any === 0 || document.querySelectorAll('article').length > 0; }})()",
            ),
        ],
    )
    scenario(
        "chosen-window-is-kept",
        "/",
        init=[FRESH],
        setup=[TWENTY_FOUR],
        wait=5,
        checks=[
            (
                "a window the reader picked is never widened for them",
                "!document.querySelector('[data-testid=widened-note]') && /Showing the last 24 hours/.test(document.querySelector('h1').closest('section').textContent) && document.querySelector('h1').textContent.trim() === \"Today's Highlights\"",
            )
        ],
    )
    scenario(
        "follow-looks-further-back",
        "/",
        init=[FRESH],
        setup=["localStorage.setItem('finn.follow.v1', JSON.stringify({companies: [], people: [], topics: ['results']})); true"],
        steps=[INTERESTED],
        wait=5,
        checks=[
            (
                "a followed topic with nothing in 24 hours still shows its filings, and says it looked further back",
                f"(async () => {{ const r24 = await {MATERIAL_IN}(24, 'results'); const r168 = await {MATERIAL_IN}(168, 'results'); const feed = document.querySelector('[data-testid=following-feed]').textContent; "
                "if (r168 === 0) return true; return r24 > 0 ? !feed.includes('looks further back') : (feed.includes('looks further back') && !feed.includes('0 filings')); })()",
            )
        ],
    )
    scenario(
        "first-visit-hint",
        "/",
        wait=5,
        checks=[
            ("a first visit shows 'Tap any card for numbers and sources'", "document.querySelector('[data-testid=first-visit-hint]').textContent.includes('Tap any card for numbers and sources')"),
            (
                "'Got it' dismisses it and it is remembered",
                "(() => { window.__byText('[data-testid=first-visit-hint] button', 'Got it').click(); return new Promise(r => setTimeout(() => r(!document.querySelector('[data-testid=first-visit-hint]') && localStorage.getItem('finn.hint.brief.v1') === '1'), 300)); })()",
            ),
        ],
    )
    scenario(
        "returning-visit-no-hint",
        "/",
        setup=["localStorage.setItem('finn.hint.brief.v1', '1'); true"],
        wait=5,
        checks=[("a returning reader does not see it", "!document.querySelector('[data-testid=first-visit-hint]')")],
    )
    scenario(
        "figures-as-printed",
        "/",
        setup=[SEVEN],
        wait=5,
        checks=[
            (
                "'Figures as printed' opens and links to the filing at that page",
                "(() => { const art = [...document.querySelectorAll('article')].find(a => a.textContent.includes('Kaynes')); "
                "const row = [...art.querySelectorAll('button[aria-expanded]')].find(x => /Q2 FY27|results/i.test(x.textContent)); row.click(); "
                "return new Promise(r => setTimeout(() => { const s = [...document.querySelectorAll('summary')].find(x => x.textContent.includes('Figures as printed')); if (!s) return r(false); s.click(); "
                "setTimeout(() => { const a = [...document.querySelectorAll('a')].find(x => x.textContent.includes('Open the filing at page')); r(!!a && /[.]pdf#page=[0-9]+/.test(a.getAttribute('href')) && a.rel.includes('noopener')); }, 300); }, 400)); })()",
            ),
        ],
    )
    scenario(
        "unprepared-ticker-makes-no-404",
        "/research?symbol=ZZZZ",
        wait=4,
        contrast=False,
        checks=[
            (
                "a ticker that was never prepared does not ask for files that do not exist",
                "performance.getEntriesByType('resource').filter(e => /[/]data[/](research[/])?ZZZZ[.]json/.test(e.name)).length === 0",
            ),
        ],
    )
