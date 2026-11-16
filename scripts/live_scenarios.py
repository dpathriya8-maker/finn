"""The screens and states scripts/check_live.py walks through. `define` is given the `scenario` registrar."""

SEVEN = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:168})); true"

# The reader's own entries (not sample): RELIANCE and HDFCBANK with a buy price, INFY with an amount only (no profit or loss).
MY_HOLDINGS = (
    "localStorage.setItem('finn.holdings.v2', JSON.stringify({"
    "RELIANCE:{amount:50000,buyPrice:1000},HDFCBANK:{amount:30000,buyPrice:1000},INFY:{amount:20000}})); true"
)

SUMMARY = "document.querySelector('[data-testid=portfolio-summary]')"


def click(selector: str, text: str) -> str:
    return f"(() => {{ const el = window.__byText({selector!r}, {text!r}); if (!el) throw new Error('no ' + {text!r}); el.click(); return true; }})()"


def stored() -> str:
    return "JSON.parse(localStorage.getItem('finn.holdings.v2') || '{}')"


def define(scenario) -> None:
    import live_scenarios_follow

    live_scenarios_follow.define(scenario)
    import live_scenarios_ready

    live_scenarios_ready.define(scenario)
    scenario("brief", "/", checks=[("summary line is shown", "!!document.querySelector('[data-testid=summary]')"),
                                   ("no portfolio card without amounts", f"!{SUMMARY}")])
    scenario("brief-open", "/", setup=[SEVEN], expand=True, wait=5, shot_name="brief-open")
    scenario("interested", "/", steps=["document.getElementById('tab-interested').click()"], expand=True)
    scenario("alerts", "/alerts")
    scenario("research", "/research")
    scenario("research-bajaj", "/research?symbol=BAJFINANCE", wait=7, expand=True)
    scenario(
        "you",
        "/settings",
        checks=[
            (
                "the You tab has its four sections (not a fixed count of three)",
                "['muted', 'investments', 'preferences', 'how'].every(id => !!document.getElementById(id)) && document.querySelectorAll('main section[id]').length >= 4",
            ),
            ("no copy says 'counts as news'", "!document.body.textContent.includes('counts as news')"),
        ],
    )

    # ---- Part A: profit and loss
    scenario(
        "portfolio",
        "/",
        setup=[SEVEN, MY_HOLDINGS],
        wait=5,
        shot_name="portfolio-summary",
        checks=[
            ("the summary card is shown", f"!!{SUMMARY}"),
            ("it has the four figures", f"['Total invested','Current value','Overall','Today'].every(t => {SUMMARY}.textContent.includes(t))"),
            ("it says 2 of 3 have a buy price", f"{SUMMARY}.textContent.includes('(2 of 3)')"),
            ("it says it is not advice", f"{SUMMARY}.textContent.includes('For understanding only, not advice')"),
            ("no sample badge on the reader's own numbers", f"!{SUMMARY}.textContent.includes('Sample')"),
            (
                "the breakdown lists the loss first, then the gain, then the one without a buy price",
                f"(() => {{ {SUMMARY}.querySelector('button').click(); return new Promise(r => setTimeout(() => {{ const li = [...{SUMMARY}.querySelectorAll('li')]; "
                "r(li.length === 3 && li[0].textContent.includes('HDFC') && li[0].textContent.includes('▼') && li[1].textContent.includes('Reliance') && li[1].textContent.includes('▲') && li[2].textContent.includes('No buy price')); }, 300)); })()",
            ),
        ],
    )
    scenario(
        "portfolio-holding-line",
        "/",
        setup=[SEVEN, MY_HOLDINGS],
        wait=5,
        checks=[
            (
                "a company header shows 'Your ₹… · … today · … overall' when there is a buy price",
                "[...document.querySelectorAll('[data-testid=holding-line]')].some(e => /Your ₹[\\d,]+\\s*· [▲▼] ₹[\\d,]+ today\\s*· [▲▼] ₹[\\d,]+ overall/.test(e.textContent.replace(/\\s+/g, ' ')))",
            ),
            (
                "no 'overall' without a buy price",
                "[...document.querySelectorAll('[data-testid=holding-line]')].filter(e => e.textContent.includes('20,000')).every(e => !e.textContent.includes('overall'))",
            ),
        ],
    )
    scenario(
        "you-invest",
        "/settings#investments",
        setup=[MY_HOLDINGS],
        steps=["document.getElementById('investments').scrollIntoView()"],
        wait=4,
        shot_name="you-investments",
        checks=[
            (
                "two boxes per company with numeric keyboards",
                "(() => { const a = document.getElementById('amount-RELIANCE'), b = document.getElementById('buy-RELIANCE'); return a.inputMode === 'decimal' && b.inputMode === 'decimal' && /Amount invested/.test(a.labels[0].textContent) && /Average buy price/.test(b.labels[0].textContent); })()",
            ),
            ("saved numbers show Indian grouping", "document.getElementById('amount-RELIANCE').value === '50,000'"),
            ("a gain shows Worth ... ▲", "/Worth ₹[\\d,]+ now.*▲/.test(document.querySelector('[data-testid=holding-hint-RELIANCE]').textContent)"),
            ("a loss shows ▼", "document.querySelector('[data-testid=holding-hint-HDFCBANK]').textContent.includes('▼')"),
            ("without a buy price it says so", "document.querySelector('[data-testid=holding-hint-INFY]').textContent.includes('Add a buy price')"),
            (
                "typing 1500000 shows 15,00,000 after leaving the box and keeps the number",
                f"(() => {{ const el = document.getElementById('amount-ITC'); el.focus(); window.__setVal(el, '1500000'); el.blur(); return new Promise(r => setTimeout(() => r(document.getElementById('amount-ITC').value === '15,00,000' && {stored()}.ITC.amount === 1500000), 300)); }})()",
            ),
            (
                "a bad price is flagged and not saved",
                f"(() => {{ const el = document.getElementById('buy-ITC'); el.focus(); window.__setVal(el, 'abc'); return new Promise(r => setTimeout(() => {{ r(el.getAttribute('aria-invalid') === 'true' && !!document.getElementById('buy-ITC-error') && {stored()}.ITC.buyPrice === undefined); }}, 300)); }})()",
            ),
            (
                "a buy price of 0 is refused",
                "(() => { const el = document.getElementById('buy-ITC'); window.__setVal(el, '0'); return new Promise(r => setTimeout(() => r(el.getAttribute('aria-invalid') === 'true'), 200)); })()",
            ),
        ],
    )
    scenario(
        "you-sample",
        "/settings#investments",
        steps=[click("button", "Try with sample holdings"), "document.getElementById('investments').scrollIntoView()"],
        wait=4,
        shot_name="you-sample",
        checks=[
            ("sample fills six companies", f"Object.keys({stored()}).length === 6"),
            ("they are all marked sample", f"Object.values({stored()}).every(h => h.sample === true && h.amount > 0 && h.buyPrice > 0)"),
            ("a 'Sample holdings' badge and a Clear button are visible", "document.getElementById('investments').textContent.includes('Sample holdings') && !!window.__byText('button', 'Clear sample')"),
            (
                "clear removes them",
                "(() => { window.__byText('button', 'Clear sample').click(); return new Promise(r => setTimeout(() => r(localStorage.getItem('finn.holdings.v2') === '{}'), 300)); })()",
            ),
        ],
    )
    scenario(
        "you-sample-confirm",
        "/settings#investments",
        setup=[MY_HOLDINGS],
        steps=[click("button", "Try with sample holdings")],
        wait=4,
        checks=[
            (
                "with the reader's own entries it asks first and changes nothing yet",
                f"!!document.querySelector('[role=alertdialog]') && {stored()}.RELIANCE.amount === 50000 && !{stored()}.RELIANCE.sample",
            ),
            (
                "'Keep mine' leaves everything as it was",
                f"(() => {{ window.__byText('button', 'Keep mine').click(); return new Promise(r => setTimeout(() => r(!document.querySelector('[role=alertdialog]') && {stored()}.RELIANCE.amount === 50000), 300)); }})()",
            ),
            (
                "'Replace with sample' replaces them",
                f"(() => {{ window.__byText('button', 'Try with sample holdings').click(); return new Promise(r => setTimeout(() => {{ window.__byText('button', 'Replace with sample').click(); setTimeout(() => r(Object.values({stored()}).every(h => h.sample === true)), 300); }}, 300)); }})()",
            ),
        ],
    )
    scenario(
        "brief-sample",
        "/",
        setup=[
            SEVEN,
            "localStorage.setItem('finn.holdings.v2', JSON.stringify({RELIANCE:{amount:50000,buyPrice:1200,sample:true},HDFCBANK:{amount:30000,buyPrice:900,sample:true}})); true",
        ],
        wait=5,
        checks=[
            ("the summary card says Sample holdings", f"{SUMMARY}.textContent.includes('Sample holdings')"),
            ("so does a company header", "[...document.querySelectorAll('[data-testid=holding-line]')].some(e => e.textContent.includes('Sample holdings'))"),
        ],
    )
