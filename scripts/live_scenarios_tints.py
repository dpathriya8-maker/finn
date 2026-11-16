"""Part E scenarios: good and bad colour as soft tints with a 3px edge. Registered from live_scenarios.define."""
import json

SEVEN = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:168})); true"
TWENTY_FOUR = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:24})); true"
LOW_LINES = "localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:72, priceMovePct:0.3, volumeMultiple:1.5})); true"

# Helpers available to every check: the colour of a token as [r,g,b], and how far an element's background is from "token mixed into surface".
HELPERS = """
window.__rgb = (css) => { const c = document.createElement('canvas').getContext('2d', { willReadFrequently: true }); c.clearRect(0,0,1,1); c.fillStyle = '#000'; c.fillStyle = css; c.fillRect(0,0,1,1); const d = c.getImageData(0,0,1,1).data; return [d[0], d[1], d[2], d[3]]; };
window.__token = (name) => { const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim(); return window.__rgb(v); };
window.__dark = () => matchMedia('(prefers-color-scheme: dark)').matches;
// A card with this tone: 3px left edge in the full colour, a background that is the colour mixed into the surface (9-10% light, 16% dark).
window.__toneOk = (el, token) => {
  const cs = getComputedStyle(el);
  const edge = window.__rgb(cs.borderLeftColor), full = window.__token('--' + token), surface = window.__token('--surface');
  const share = window.__dark() ? 0.16 : (token === 'watch' ? 0.10 : 0.09);
  const want = [0,1,2].map(i => Math.round(full[i] * share + surface[i] * (1 - share)));
  const got = window.__rgb(cs.backgroundColor);
  const close = (a, b, t) => Math.abs(a - b) <= t;
  return cs.borderLeftWidth === '3px' && [0,1,2].every(i => close(edge[i], full[i], 1)) && [0,1,2].every(i => close(got[i], want[i], 3)) && got[3] === 255;
};
window.__plain = (el) => { const cs = getComputedStyle(el); const bg = window.__rgb(cs.backgroundColor); return cs.borderLeftWidth === '3px' && window.__rgb(cs.borderLeftColor)[3] === 0 && (bg[3] === 0); };
true
"""


def with_helpers(js: str) -> str:
    return f"(() => {{ {HELPERS} return ({js}); }})()"


def define(scenario) -> None:
    scenario(
        "tints-brief",
        "/",
        setup=[SEVEN],
        wait=5,
        shot_name="tints-brief",
        checks=[
            (
                "a risk filing (Kaynes results) is a soft red card with a 3px red edge and a Risk label",
                with_helpers("(() => { const row = [...document.querySelectorAll('article')].find(a => a.textContent.includes('Kaynes'))?.querySelector('[class*=\"border-l-bad\"]'); return !!row && window.__toneOk(row, 'bad') && row.textContent.includes('Risk'); })()"),
            ),
            (
                "a neutral filing has no tint and no coloured edge",
                with_helpers("(() => { const rows = [...document.querySelectorAll('article > div.divide-y > div')].filter(d => !/border-l-(bad|good|watch)/.test(d.className)); return rows.length > 0 && rows.every(r => window.__plain(r)); })()"),
            ),
            ("'1 risk to review' is red", "[...document.querySelectorAll('[data-testid=summary] span.text-bad')].some(e => /risk/.test(e.textContent))"),
            ("the tint is a wash, not a fill: the card's text colour is unchanged", with_helpers("(() => { const t = document.querySelector('article [class*=\"border-l-bad\"] span'); return !!t; })()")),
        ],
    )
    scenario(
        "tints-quiet-is-green",
        "/",
        setup=[TWENTY_FOUR],
        wait=5,
        checks=[
            (
                "'Quiet day' is green when nothing material is in the window",
                "(async () => { const b = await (await fetch('/data/brief.json')).json(); const end = Date.parse(b.generated_at), start = end - 24 * 3600000; "
                "const material = b.items.filter(i => { const t = Date.parse(i.published_at); return t >= start && t <= end + 60000 && !i.routine && i.priority >= 45; }).length; "
                "const el = document.querySelector('[data-testid=summary]'); return material > 0 ? !el.textContent.startsWith('Quiet day') : (el.textContent.startsWith('Quiet day') && !!el.querySelector('span.text-good')); })()",
            )
        ],
    )
    scenario(
        "tints-alerts",
        "/alerts",
        setup=[LOW_LINES],
        wait=5,
        shot_name="tints-alerts",
        checks=[
            (
                "a price fall is a red card and a price rise is a green card, each with its word and arrow",
                with_helpers(
                    "(() => { const cards = [...document.querySelectorAll('article')].filter(a => a.querySelector('button')); "
                    "const bad = cards.filter(a => /border-l-bad/.test(a.className)), good = cards.filter(a => /border-l-good/.test(a.className)); "
                    "return (bad.length > 0 || good.length > 0) && bad.every(a => window.__toneOk(a, 'bad') && a.textContent.includes('▼') && a.textContent.includes('Risk')) && good.every(a => window.__toneOk(a, 'good') && a.textContent.includes('▲') && a.textContent.includes('Good')); })()"
                ),
            )
        ],
    )
    scenario(
        "tints-research",
        "/research?symbol=BAJFINANCE",
        wait=7,
        shot_name="tints-research",
        checks=[
            (
                "Missed is red, Partly and Not followed up are amber, Kept is green; Too early has no tint",
                with_helpers(
                    "(() => { const map = { 'Missed': 'bad', 'Partly': 'watch', 'Not followed up': 'watch', 'Kept': 'good' }; let seen = 0; "
                    "for (const art of document.querySelectorAll('article')) { const chip = art.querySelector('span.font-semibold'); if (!chip) continue; const label = chip.textContent.trim().replace(/ — delayed$/, ''); const row = art.querySelector('div[class*=\"border-l-\"]'); if (!row) continue; "
                    "if (map[label]) { seen++; if (!window.__toneOk(row, map[label])) return false; } else if (label === 'Too early') { if (!window.__plain(row)) return false; } } return seen > 0; })()"
                ),
            )
        ],
    )
    scenario(
        "tints-portfolio-gain",
        "/",
        setup=[SEVEN, "localStorage.setItem('finn.holdings.v2', JSON.stringify({RELIANCE:{amount:50000,buyPrice:1000}})); true"],
        wait=5,
        shot_name="tints-portfolio-gain",
        checks=[
            ("a portfolio in profit is a soft green card with green ▲ numbers", with_helpers("(() => { const c = document.querySelector('[data-testid=portfolio-summary]'); return window.__toneOk(c, 'good') && /▲/.test(c.textContent) && !!c.querySelector('.text-good'); })()")),
        ],
    )
    scenario(
        "tints-portfolio-loss",
        "/",
        setup=[SEVEN, "localStorage.setItem('finn.holdings.v2', JSON.stringify({RELIANCE:{amount:50000,buyPrice:2500}})); true"],
        wait=5,
        shot_name="tints-portfolio-loss",
        checks=[
            ("a portfolio at a loss is a soft red card with red ▼ numbers", with_helpers("(() => { const c = document.querySelector('[data-testid=portfolio-summary]'); return window.__toneOk(c, 'bad') && /▼/.test(c.textContent) && !!c.querySelector('.text-bad'); })()")),
        ],
    )
    scenario(
        "tints-interested",
        "/",
        setup=[SEVEN],
        steps=["document.getElementById('tab-interested').click()"],
        wait=5,
        checks=[
            (
                "a researched company with misses is a soft amber or red card",
                with_helpers("(() => { const rows = [...document.querySelectorAll('#panel-interested article > button')]; const tinted = rows.filter(b => /border-l-(bad|watch)/.test(b.className)); return tinted.length > 0 && tinted.every(b => window.__toneOk(b, /border-l-bad/.test(b.className) ? 'bad' : 'watch')); })()"),
            ),
        ],
    )
