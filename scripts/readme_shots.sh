#!/usr/bin/env bash
# Retakes the README screenshots (docs/screens/) from a running app at phone width, light mode.
#   bash scripts/readme_shots.sh https://finn-mocha.vercel.app
# Needs Edge or Chrome; see scripts/shoot.py. The Brief is shown with a 7-day window so the results and management cards are in it.
set -euo pipefail
BASE="${1:-http://localhost:3000}"
PY="${PYTHON:-backend/.venv/Scripts/python}"
OUT="docs/screens"
WAIT="new Promise(r=>setTimeout(r,1800))"
SEVEN="localStorage.setItem('finn.settings.v1', JSON.stringify({windowHours:168})); location.reload()"
OPEN_CARD="(()=>{const a=[...document.querySelectorAll('article button')].find(b=>b.textContent.includes(\"__WORD__\")); if(a) a.click()})()"

shot() { "$PY" scripts/shoot.py "$@"; }

shot "$BASE/" "$OUT/01-brief-light.png" --wait 6 --max-height 1500
shot "$BASE/" "$OUT/02-results-card-light.png" --wait 5 --js "$SEVEN" --js "$WAIT" --js "${OPEN_CARD/__WORD__/Results}" --js "$WAIT" --max-height 2300
shot "$BASE/" "$OUT/03-management-card-light.png" --wait 5 --js "$SEVEN" --js "$WAIT" --js "${OPEN_CARD/__WORD__/People}" --js "$WAIT" --max-height 2300
shot "$BASE/alerts" "$OUT/04-alerts-light.png" --wait 6 --max-height 1800
shot "$BASE/research" "$OUT/05-research-light.png" --wait 6 --max-height 1500
shot "$BASE/research?symbol=BAJFINANCE" "$OUT/06-research-company-light.png" --wait 8 --max-height 2300
shot "$BASE/settings" "$OUT/07-settings-light.png" --wait 5 --max-height 1800   # the You tab (it was called Settings)
shot "$BASE/" "$OUT/08-interested-light.png" --wait 6 --js "document.getElementById('tab-interested').click()" --js "$WAIT" --max-height 2300
shot "$BASE/" "$OUT/09-window-sheet-dark.png" --dark --wait 6 --js "document.querySelector('button[aria-label=\"Change the time window\"]').click()" --js "$WAIT" --max-height 1200
# A company that was never prepared, researched live through the deployed engine (waits for the research to finish)
shot "$BASE/research?symbol=TITAN" "$OUT/10-live-research-titan-light.png" --wait 45 --max-height 2300
