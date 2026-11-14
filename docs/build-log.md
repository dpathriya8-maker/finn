# Build log

One entry per step: what was asked, what was done, what went wrong. Newest at the bottom.

## Step 1: Scaffold and security baseline (2026-11-15)

**Asked:** the folder structure from CLAUDE.md section 4, `.gitignore`, `.env.example`, a secret-check script installed as a pre-commit hook, the portfolio / research / categories / defaults config, a README stub, decisions and this log, then commit and push. No product features.

**Done:**
- Scaffolded every folder from CLAUDE.md section 4. Python modules hold a one-line docstring; empty frontend folders hold a `.gitkeep`.
- `.gitignore` (ignores `.env*`, keeps `.env.example`), `.gitattributes` (LF line endings), `.env.example` (names only).
- `scripts/check-secrets.sh` and `scripts/install-hooks.sh`. The scanner also has an `--all` mode for CI.
- `config/`: 18-company portfolio, 4 research companies, 17 announcement categories (weight, routine flag, alert default, card type, rationale) and the smart defaults (24 h window, 2x volume, 5% move, 20-day lookback).
- `backend/tests/test_config.py`: 7 standard-library tests over the config files.
- README stub and `docs/` (decisions, data-sources, architecture, cost, this log).

**Verified:**
- `git check-ignore -v .env` matches `.gitignore:2:.env*`, and `.env.example` is not ignored.
- A real `git commit` was blocked by the installed hook while fake Google, Groq, Tavily and `sk-` keys, a password assignment, a random token and a `.env` file were staged. The output named file, line and rule and printed no key material. A line marked `secret-check:allow` was skipped.
- The scanner raised no false positives on: a BSE-style URL with a long token, a lockfile hash, a sha256, a hyphenated word ending in "sk", variable references on the right of `api_key =`, and a GitHub Actions `secrets.` expression.
- `py -m unittest discover -s backend/tests`: 7 tests OK.

**Issues:**
- Step 0 had not been done: there was no GitHub repo yet and git had no identity. The repo was initialised locally first, then created as an empty public repo with the `gh` CLI. Commits use a repo-local GitHub noreply identity because the repo is public.
- GitHub rejected the first push because the `gh` token has no `workflow` scope, so the one-job CI workflow (secret scan with `--all`) was taken out of the commit. To add it later, run `gh auth refresh -h github.com -s workflow` once. The same scope is needed for the GitHub Actions source probe in Step 3 and for a scheduled pipeline run.
- The first scanner took 35 s per run on Windows, because it started about 15 processes per file. It now exports the staged files once and runs three recursive greps: 0.7 s, same detections. It also refuses to report "clean" if its export is incomplete.
- `python` is not on PATH on this machine (a Microsoft Store alias); `py` works (Python 3.14).
- Symbols and `size_bucket` labels in `config/` are not verified against live data yet. That is Step 3.

## Step 2: Walking skeleton (2026-11-15)

**Asked:** FastAPI `/health` with CORS and a per-IP rate limit; a mobile-first Next.js page with an engine status pill, a bottom nav, a static `meta.json` ("Data as of") and a PWA manifest with icons; verify locally; deploy to Render and Vercel. Deployment was postponed by the owner, so this step ends after local verification and a ready-to-follow deploy guide.

**Done:**
- Backend: `GET /health` (status, version, IST time); CORS from `ALLOWED_ORIGINS` plus localhost, never `*`; per-IP limit of 30/min that exempts `/health`; ticker validation and an admin-token check ready for later steps; exact pins in `requirements.txt`; `render.yaml` (free plan, Singapore, `rootDir: backend`).
- Frontend: Next.js 16 (App Router, TypeScript, Tailwind 4) in a 430px phone column; status pill (checking, online, waking up, offline with Retry, not configured); bottom nav with Brief active; "Data as of" read at run time from `public/data/meta.json` and tagged "Sample data"; PWA manifest and generated icons; exact version pins.
- `docs/deploy.md`: click-by-click steps for Render, Vercel and CORS, with a troubleshooting table.

**Verified:**
- Backend: 22 pytest tests pass. On a live server `/health` returns 200; CORS allows the configured origin and localhost and blocks others; 30 requests succeed and the 31st gets 429; `/health` is never limited.
- Frontend: lint, type-check and production build pass. Seven real-browser checks (Playwright, 390px phone and 1280px desktop) pass, including a true 90 s run in which the pill showed "waking up", retried every 5 s (20 attempts), went "offline" at 91 s without moving the page, and recovered when Retry was tapped. Also checked: missing `meta.json`, dark mode, no horizontal scroll, no console errors, and "not configured" on a build without the API URL.
- Also over HTTP: manifest, icons and `meta.json` are served with the right content types, and the security headers are present.

**Not done (waiting on the owner):** the Render and Vercel deployments, so there is no live URL and the "opens on a phone" check is untested. The CI workflow still needs the GitHub `workflow` scope.

**Issues:**
- `LayoutProps`, a type Next generates at build time, broke `tsc` on a fresh checkout; replaced with an explicit props type.
- The Retry button was taller than the pill and moved the page down 12 px when the pill went offline. Fixed with a fixed-height header row, and the browser test now asserts no shift.
- Starlette now recommends `httpx2` for its test client, so the dev requirements use it.
- npm marks ESLint 9.39.5 as out of support. It is kept as chosen by create-next-app; upgrading is deferred rather than done blind.

## Step 3: Data-source spike (2026-11-15)

**Asked:** test yfinance, the NSE-to-BSE symbol mapping, BSE announcements, results PDFs, concall transcripts, the NSE API, Gemini and Groq, and Tavily for RELIANCE, KAYNES and BAJFINANCE; record findings in `docs/data-sources.md` with a Source / Laptop / Render / GitHub Actions table; build a temporary admin-only `/debug/sources` route for Render.

**Done:**
- Probed every source that needs no key, from the laptop. Findings, numbers and a draft category mapping are in `docs/data-sources.md`.
- Turned the probes into reusable code: a safe fetch layer (`app/core/http.py`: host allow-list, redirect re-checks, 25 MB cap), clients for BSE, NSE, Yahoo and the ISIN symbol join, and `probes/` with a runner (`python -m probes.run_probes`).
- `GET /debug/sources` (admin token, hidden from the API docs) runs the same probes on whatever machine hosts it.
- Pinned backend requirements built from a clean venv: runtime, plus dev tooling.

**Verified:**
- `python -m probes.run_probes` for RELIANCE, KAYNES, BAJFINANCE and CDSL: 29 of 32 probes pass. The 3 failures are the expected "CDSL has no BSE scrip" result; CDSL's NSE and screener.in probes pass.
- A brand-new venv built only from `requirements-dev.txt`: `pip check` clean, 74 tests pass, and the installed set equals the pinned set.
- Real PDFs: 3 results filings and 3 transcripts downloaded and text-extracted; results numbers cross-checked against Yahoo (Reliance and Bajaj PBT match exactly).

**Not done:**
- Render column: waits for the deploy (`docs/deploy.md` section E).
- GitHub Actions column: needs the `workflow` scope on the GitHub login.
- Gemini, Groq and Tavily: no API keys exist yet. Provider-documented limits are recorded, marked unverified.

**Issues:**
- BSE answers 403 unless User-Agent, Referer, Origin and Accept are all sent. A 15-month range returns 400 because the limit is 365 days.
- CDSL is not in BSE's scrip master. The ISIN join leaves it unmapped rather than guessing.
- A first pagination design counted raw rows and could have stopped early if a filing landed mid-read; a test caught it, and the client now counts unique IDs.
- PyMuPDF 2.1 pulled in onnxruntime and networkx; pinned the light 1.28 line instead.
- Two further probes (a parallel burst test, and a search for the minimal header set) were blocked by the environment's permission check and were not run. Rate behaviour is recorded as "not stress-tested", which is also the polite choice for a third party's API.
- Two sample files landed in `backend/` by mistake and were moved out before committing.

## Step 4: Data layer, end to end (2026-11-15)

**Asked:** prices, announcements and documents for one company through to a JSON file the app shows; the milestone is a real `RELIANCE.json` in the app.

**Done:**
- `python -m pipeline.run` builds, for each company: announcements (BSE, or NSE when BSE does not list it), 3 months of prices, the raw EOD signals (price move, volume against the 20-day average), and Yahoo's quarterly figures for later cross-checks. Output goes to `frontend/public/data/`: `<SYMBOL>.json` per company (22 files with the research companies), `brief.json` (all portfolio filings plus signals) and `meta.json`.
- A failing source keeps the last good data and is flagged `stale` with the time of that data; files are written atomically.
- The app reads `meta.json` and `brief.json` at run time through a typed hook and lists the latest filings. The "Sample data" tag is gone because the data is real.

**Verified:**
- A live run for all 22 companies took 26 s and had no problems (107 portfolio filings in 14 days, 73 KB). CDSL came from NSE, the other 17 portfolio companies from BSE.
- 97 backend tests pass, 23 of them new: signal maths (including a split not counting as a move), source selection, BSE and NSE retries, graceful failure with stale data, and the files written.
- Frontend lint, type-check and build pass; a phone-size screenshot shows real filings and no console errors.

**Issues:**
- BSE answered one valid BAJFINANCE request with HTTP 400. The identical request then worked four times in a row, so it was transient. NSE covered it that run, and a short retry now handles it.
- Yahoo's prices carry float noise (`1335.4000244140625`); values are rounded when stored.
- The list is chronological and repetitive ("Announcement under Regulation 30 (LODR)-Newspaper Publication"). That is the problem Step 5 (classifier and priority) is for.

## Step 5: Classifier and priority with a visible reason (2026-11-15)

**Asked:** classify every filing (rules first, a cheap model only if needed), give each a priority score with a visible "why", for all 18 companies.

**Done:**
- `app/push/classify.py`: Tier 0 classifier, no model. Exact label tables for BSE (75 labels) and NSE (59), keyword rules for the vague labels, and refiners that move good and bad news apart (downgrade versus reaffirmation, key-person exit versus hire, pledge invoked versus released).
- `app/push/priority.py`: score 0 to 100 plus a one-line `why`; `app/push/headline.py`: a readable one-line headline from the subject or the body; `app/push/categories.py` reads `config/categories.json`, which now has a short `why` per category.
- Every item in `brief.json` and the company files now carries `category`, `priority`, `routine`, `why`, `headline` and the `rule` that decided it. A results filing posted twice is shown once.

**Verified:**
- 183 backend tests pass (86 new): every exchange label maps to a real category; the negativity-bias ordering (downgrade over upgrade over reaffirmation, CFO exit over CFO appointment, pledge invoked over created over released, litigation over results over dividend); routine collapsing; the headline cases below.
- On real data, 3,570 filings (one BSE day of 1,920, one NSE day of 987, 18 months of three companies): 35 to 56% are routine, and 10 to 17% of non-routine filings stay unclassified, mostly board outcomes whose text is empty. Only 18 BSE filings (0.5%) carried a label not in the table, and no NSE filing did.
- Live run: all 18 portfolio companies have classified filings (102 in 14 days; 63 routine; 15 high, 7 medium and 17 low priority among the rest).

**Issues found by reading real output, and fixed:**
- Maruti's "Reference to the Financial Results Issued by Suzuki Motor Corporation" was ranked as Maruti's own results (88); the results keyword rule is stricter now and skips results "issued by" someone else.
- A subsidiary's "voluntary winding up" was flagged as litigation; "Withdrawal of Credit Rating" scored like a downgrade; "Appointment of Internal Auditor" scored like a key-person change.
- Headlines were cut at "Mr." and "V."; "?10/-" should be "₹10/-"; "As per annexure enclosed" and "Please refer the enclosed file" are not headlines; BSE shouts "12TH" and "30Th".

**Limits, stated plainly:**
- Quality was judged by reading samples; there is no labelled test set, so accuracy is not measured.
- Pledging has no real example in about 3,500 filings, so its rule is covered by written wording only.
- About a sixth of non-routine filings stay `unclassified`; they are visible at low priority, not hidden.

## Step 6: The Morning Brief screen (2026-11-15)

**Asked:** a window selector, priority groups, a collapsed routine row and an "all caught up" ending; it has to work on a phone.

**Done:**
- The Brief screen: a 24 hours / 3 days / 7 days picker (default 24 hours), "N things that matter", then "Needs attention" and "Worth a look" (at most five cards each, the rest behind "Show N more"), a collapsed "N lower-priority filings" row, a collapsed "N routine filings" row, and "You're all caught up" with the time it was checked.
- Each card shows the headline first, then a one-line reason it ranked where it did; tapping opens the details, the filing itself and exactly how it was ranked and labelled by the exchange. Headline size follows priority.
- Colour only for meaning: the classifier now gives each filing a `tone`; red, amber and green appear with a "Risk", "Watch" or "Good news" tag.
- Empty window: says so and offers "Look back 3 days". Stale data, a failed load, corrupt saved settings and muted companies are all handled and announced, never silent.
- Settings storage (window, thresholds, category alerts, muted companies) with validated localStorage; the pipeline publishes `config.json` so the deployed app does not need files outside its folder.

**Verified:**
- Backend 191 tests. Frontend: 19 unit tests (window maths, grouping order, India-calendar day labels, settings validation), lint, type-check and production build.
- 11 behaviour checks in a real phone-sized Chromium: card opens and closes from the keyboard, the five-card cap, collapsed routine rows, the empty state, tone tags in light and dark, stale banner, failed load, a muted company disappearing, a bad stored setting ignored, the chosen window surviving a reload, no horizontal scroll and no console errors.
- I looked at the screenshots at 390 px, light and dark.

**Issues found and fixed:**
- "1 lower-priority filings" (plural bug).
- HDFC Bank's re-appointment of a whole-time director sat under "Needs attention" at 85; re-appointments now rank below new hires.
- vitest 5 needs `@types/node` 22 or newer and the project pinned 20, so npm refused to install it. I moved the types package to 22 (no runtime change) instead of forcing the install.

**Not built yet:** the Alerts, Research and Settings tabs (Steps 7 and 10), so a company can be muted in storage but not yet from a screen.
