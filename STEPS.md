# FINN: Step-by-step build plan

**How we work:** one step at a time. You paste the step prompt into Claude Code (VS Code). Claude Code finishes with a `STEP REPORT`. You paste that report into the planning chat. I review it and write the next prompt, adjusted to what actually happened.
Only Steps 1–3 are written in full below. Steps 4+ depend on what Step 3 finds about data sources, so those prompts get written after it.

**Claude Code tips (they save credits):**
- Run `/clear` after every step. `CLAUDE.md` reloads automatically, so no context is lost.
- For big steps, press Shift+Tab for plan mode. Approve the plan, then let it build.
- Don't paste long logs. Ask Claude Code to summarise them.

---

## Step 0: You, by hand (~20 min). No coding.
- [ ] GitHub → New repository `finn` under `dpathriya8-maker`. Make it **Public** (ENAM must be able to open it). Leave it **empty**: no README, no .gitignore.
- [ ] Clone it into a local folder, then copy `CLAUDE.md` and `STEPS.md` into the repo root.
- [ ] Install or check: Node 20+, Python 3.11+, Git, VS Code with the Claude Code extension.
- [ ] Sign up with GitHub login at **Vercel** (vercel.com) and **Render** (render.com). Both are free and need no card.
- [ ] Get API keys:
  - **Google AI Studio** (aistudio.google.com) → Get API key. Also note which Flash and Flash-Lite model names it shows as free, and their limits.
  - **Groq** (console.groq.com) → API key. This is the fallback LLM.
  - **Tavily** (app.tavily.com) → API key, for management bios. 1,000 free credits a month.
- [ ] In the repo root, create a file named `.env` and put the keys in it. **Never paste keys into any chat.** Your chats go to ENAM as build history.
- [ ] Open the repo folder in VS Code and start Claude Code.

---

## Step 1: Scaffold and security baseline (~30 min)
**Paste into Claude Code:**
```
Read CLAUDE.md fully. This is Step 1: scaffold + security baseline. No product features yet.

1. Create the folder structure from CLAUDE.md section 4 (empty modules with a one-line docstring are fine).
2. .gitignore covering: .env*, !.env.example, node_modules, .next, __pycache__, .venv, *.sqlite, *.db, cache/, *.pdf downloads, .DS_Store.
   Then confirm .env is ignored with `git check-ignore .env`.
3. .env.example with names only: GEMINI_API_KEY, GROQ_API_KEY, TAVILY_API_KEY, LLM_CHEAP_MODEL, LLM_STRONG_MODEL, LLM_FALLBACK_MODEL, ADMIN_TOKEN, ALLOWED_ORIGINS, DAILY_FRESH_RESEARCH_CAP.
4. scripts/check-secrets.sh: scans staged files for key-like patterns (AIza..., gsk_..., tvly-..., sk-..., long base64-ish tokens) and for any .env file; exits non-zero if found.
   Install it as a git pre-commit hook (scripts/install-hooks.sh) and run it once to prove it works (test with a fake key in a temp file, then delete it).
5. config/portfolio.json — 18 NSE companies, each {symbol, name, sector, size_bucket}:
   RELIANCE, HDFCBANK, INFY, ITC, LT, SUNPHARMA, MARUTI, BHARTIARTL, TATASTEEL (large),
   POLYCAB, DIXON, PERSISTENT, TRENT, CHOLAFIN, APOLLOHOSP (mid),
   CDSL, KAYNES, DEEPAKNTR (smaller).
   config/research.json — BAJFINANCE, ASIANPAINT, HAL, NAUKRI (research demo, outside portfolio).
   Don't verify symbols yet — Step 3 does that.
6. config/categories.json — the 17 categories from the ENAM reference (results, M&A, fund_raise, management_change, litigation,
   insider_trading, earnings_call, investor_meetings, credit_rating, dividend, bonus_split, capex, press_release, postal_ballot,
   agm_egm, pledging, unclassified), each with: weight (0–100), is_routine (bool), default_alert (bool), card_type
   ("results" | "management" | "one_liner" | "surface_only"), plus a one-line rationale. Use your judgment; negativity bias
   means litigation/pledging/credit downgrades rank high.
   config/defaults.json — window_hours 24, volume_multiple 2.0, price_move_pct 5.0, volume_lookback_days 20.
7. README.md stub (title, one-line pitch, "work in progress").
8. docs/decisions.md with the decisions already made in CLAUDE.md; docs/build-log.md with a Step 1 entry.
9. Commit ("chore: scaffold + security baseline") and push to origin main.

Do NOT create the Next.js or FastAPI apps yet beyond empty folders. End with the STEP REPORT.
```
**Done when:** the repo on GitHub shows the folders, no `.env` is in it, and the pre-commit hook blocks a fake key.

---

## Step 2: Walking skeleton, deployed (M0, ~60 min)
**Paste into Claude Code:**
```
Read CLAUDE.md. This is Step 2: walking skeleton, deployed end to end. Keep it minimal.

Backend (backend/):
- FastAPI app with GET /health → {status:"ok", version, time_ist}. CORS from ALLOWED_ORIGINS env (comma list).
- Per-IP rate limit (e.g. slowapi, 30/min default). Pinned requirements.txt. Runs with `uvicorn app.main:app`.
- render.yaml at repo root: free web service, region singapore, rootDir backend, healthCheckPath /health, env vars listed
  as sync:false (no values).

Frontend (frontend/):
- Next.js (App Router, TypeScript, Tailwind), mobile-first, max-width ~430px centred on desktop.
- One page: app name "FINN", a status pill that calls the backend /health (NEXT_PUBLIC_API_URL) and shows
  "Engine online" (green) / "Engine waking up…" (amber, retry every 5s for up to 90s) / "Engine offline" (red).
- Bottom nav placeholder: Brief · Alerts · Research · Settings (only Brief active).
- Also read a static file public/data/meta.json ({generated_at:"…", note:"skeleton"}) and show "Data as of …" — this proves
  the static-JSON path we'll use for Push.
- Basic PWA manifest + icons so it can be "Add to Home Screen".

Verify locally (both servers), then:
- Give me exact click-by-click steps to deploy backend on Render (Blueprint from render.yaml) and frontend on Vercel
  (root directory = frontend), including which env vars to set where. Wait for me to confirm the URLs.
- After I give you the URLs: set ALLOWED_ORIGINS / NEXT_PUBLIC_API_URL correctly, redeploy, and confirm the live page
  shows "Engine online". Run the secret check, commit, push. Update docs/build-log.md. End with the STEP REPORT.
```
**Done when:** the Vercel link opens on your phone and shows "Engine online" plus "Data as of …".

---

## Step 3: Data-source spike. Verify before we build (~45–60 min)
This step decides the architecture, so it's the most important one so far.
**Paste into Claude Code:**
```
Read CLAUDE.md. This is Step 3: a verification spike. No UI. Write throwaway-but-clean probe scripts in backend/probes/
and record findings in docs/data-sources.md. Test from THIS laptop first.

For RELIANCE and for one smaller company (KAYNES), and for one research company (BAJFINANCE), test and report:
1. yfinance: last 30 trading days OHLCV for .NS (and .BO fallback). Also check whether yfinance quarterly income
   statement gives Revenue / EBITDA / Pretax Income / Net Income for the last 5 quarters (for cross-checking results).
2. NSE symbol → BSE scrip code mapping that works for ANY ticker (try BSE scrip master / ISIN route; the `bse` PyPI
   package is acceptable if it works). Report which method works.
3. BSE announcements API for the last 7 days and last 90 days by scrip code: response shape, fields available
   (category, subcategory, headline, attachment PDF URL, datetime), pagination, required headers, rate behaviour.
   List the distinct category/subcategory values you see — we'll map them to our 17 categories.
4. Results filing: find the latest quarterly results PDF via announcements. Download it. Is it text-extractable
   (PyMuPDF) or scanned? Can you locate Revenue / EBITDA-or-components / PBT / PAT for current qtr, prev qtr, same qtr
   last year from the text? (Just report feasibility + where the numbers sit; don't build the extractor.)
5. Concall transcripts: can you find the last 4 quarters' transcript PDFs via BSE announcements (earnings_call)?
   If not, try screener.in company page links. Report hit rate and text quality.
6. NSE announcements API as fallback: does it work from this laptop? (Do not bypass CAPTCHAs.)
7. Gemini: list the models my key can use for free (models.list) and make one tiny test call to the cheap and strong
   candidates; record exact model names and any rate-limit info. Same for Groq. Put the chosen names in .env (not in git).
8. Tavily: one test search "<name> appointed CFO <company>" and report result quality. Use 1–2 credits only.

Then deploy a TEMPORARY admin-only endpoint GET /debug/sources (requires ADMIN_TOKEN header) on Render that runs
probes 1, 3 and 5 with tiny payloads, and report which ones work from Render's server (Singapore).
Also tell me whether a GitHub Actions runner could reach yfinance and BSE (try it with a manual workflow_dispatch probe
workflow if quick; otherwise say "untested").

docs/data-sources.md must end with a table: Source | Laptop | Render | GitHub Actions | Notes / fallback.
Remove nothing secret into git. Commit, push, update build-log. End with the STEP REPORT (include the table).
```
**Done when:** the table is filled in and we know exactly which source works from where.

---

## Steps 4–11: outline (full prompts after Step 3)
| # | Step | Milestone | Done when |
|---|---|---|---|
| 4 | Data layer for 1 company end-to-end: prices, announcements, docs, then JSON | M1 | `public/data/RELIANCE.json` is real and shown in the app |
| 5 | Classifier (rules first, cheap LLM fallback) + priority score with a visible "why" | M2 | All 18 companies have classified, ranked filings |
| 6 | Morning Brief UI: window selector, priority groups, collapsed routine, "all caught up" | M2 | Works on your phone |
| 7 | Alerts: EOD signals + category preferences, thresholds in Settings, mute a company | M2 | Changing a threshold changes the alerts instantly |
| 8 | Results card (QoQ/YoY, deltas computed in code, ✓ cross-check) + management bio card | M2 | Real cards for companies that reported this week |
| 9 | Pull engine: transcript ingestion, chunking, Promise Tracker for 1 company, then any ticker | M3 | Works on a ticker we never precomputed |
| 10 | Research UI: scorecard, quote + page, "Ask the documents" | M3 | Every claim links to its source |
| 11 | Polish + 390px phone test, then README, architecture diagram, cost table, write-up, build history | M4–M5 | Submission email ready |

**Rough clock (IST):** Step 0–1 by 02:30 · Step 2 by 03:30 · Step 3 by 04:30 · Steps 4–8 by 13:00 · Steps 9–10 by 17:30 · Step 11 by 20:30 · send by 21:00.
