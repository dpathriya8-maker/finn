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

## Step 7: Alerts, thresholds and muting (2026-11-15)

**Asked:** unusual end-of-day moves and chosen announcement categories as alerts, thresholds in Settings, a way to mute a company; changing a threshold must change the alerts instantly.

**Done:**
- Alerts tab: price and volume alerts (a move or volume more than the user's line), then the filings in the categories the user switched on. Each alert shows its reason in the user's own terms ("Moved more than ±3% in a day, your line") and the numbers behind it on tap (a table of recent sessions with the triggering day highlighted). Risks come first.
- Settings tab: time window, a price-move slider (1 to 15%, default 5) and a volume slider (1.5 to 10 times, default 2) each showing its value, range and default, a live line ("With these lines, 1 price or volume alert and 2 filings in the last 24 hours"), 17 category switches (risks first, 8 on by default), the 18 companies with a mute switch, a reset button and a plain statement that nothing is stored on a server.
- Muting also works from any card ("Mute RELIANCE"), and the Brief says when companies are muted and links to where to undo it.
- The tab bar's Alerts icon shows the current alert count. The header, status pill and tab bar moved into the layout so they persist across tabs.
- The app says plainly that there are no push notifications: it checks when opened.

**Verified:**
- 39 frontend unit tests (the alert rules, boundaries, window-to-session mapping, mutes, ordering, and that lowering a threshold raises the count), lint, type-check, production build with `/alerts` and `/settings` as static pages.
- 9 real-browser checks, including the done-when: with the page open, a keyboard slider move from 5% to 3% changes the live preview, then tapping the Alerts tab (no reload) shows 3 alerts and the tab badge reads 3; raising the volume line lowers it again; the choice survives a reload. Also: tabs navigate and mark the current one with a single engine check across four screens, a category switch changes what Alerts lists, muting from a card removes the company everywhere and can be undone, reset restores every default, switches work from the keyboard, the empty state, real data in light and dark with no overflow or console errors.
- The Step 6 Brief checks (11) still pass.

**Real-data note:** at the default lines (5% and 2 times) the whole portfolio produced one alert on the latest session, a quiet market with a largest move of 3.8%. At 3% and 1.5 times it produces 15 over the stored sessions. The sliders are therefore meaningful, not decorative.

**Limits:** price and volume come from five stored sessions per company, so a 7-day window looks at five sessions at most; Yahoo's volume figures are not exchange-official.

## Step 8: Results and management cards (2026-11-15)

**Asked:** a results card (Revenue, EBITDA, PBT, PAT, quarter on quarter and year on year, from the actual filing, with a check against another source) and a management-change card (who, and a short bio of the incoming person).

**Done:**
- **Results card, no model.** Figures are read from the PDF by word position, converted to Rs crore, and every changed figure is computed in code. The card shows the numbers in a table (EBITDA marked as computed), margins, the page and the filing's own printed tokens one tap down, and a badge: matches Yahoo Finance, differs, or not cross-checked, always in words. Scanned filings show only what Yahoo confirms; a scan nothing can confirm is refused with a reason.
- **Management card, no model.** Person, role, effective date, term, DIN and the filing's own "Profile" section (with its page), all literal spans of the filing. Its facts raise the rank of a key person leaving and replace a vague or cut-short headline with a real one.
- **Pipeline:** downloads each results or management filing through the safe fetch (allow-list, 25 MB cap, `AttachLive` then `AttachHis`), once per file per company per run; keeps what it read in a SQLite cache (`backend/.cache`, git-ignored) so a second run downloads nothing; rebuilds each card every run so the Yahoo check stays current. A failure becomes a card that says so, and a good card from the previous run survives a failed download.
- **App:** both cards inside the existing filing card (headline first, numbers one tap down, source one more); the Brief and Alerts show them the same way.
- Also: `app/core/cache.py` (SQLite key-value, never a point of failure) and `app/sources/documents.py` are now real.

**Real data (18 companies, 28 seconds cold, 0 problems):** 3 results cards in full (ITC, Tata Steel, Kaynes), 1 partial (Bharti Airtel, a scan: PBT only), 1 refusal (Apollo Hospitals, a scan nothing can confirm); 4 management cards (HDFC Bank twice, Tata Steel, Apollo Hospitals). Apollo's CEO-division exit went from "Change in Management", 85, neutral to a named headline at 97 as a risk.

**Verified:**
- Backend 389 tests (was 191): seven real results filings (word positions cut from them as fixtures), four real management filings, synthetic PDFs including pages drawn sideways and shown through /Rotate, the safety rules one by one, the cache, the downloader, the pipeline end to end.
- Frontend 57 unit tests, lint, type-check, production build.
- 17 checks in a real phone-sized Chromium on the real data: each card type opens and shows the right numbers and words, the headline is a sentence not a label, badges carry text as well as colour, no overflow at 390 px, tap targets at least 44 px, tables are real tables for screen readers, dark mode, and a filing with no card stays a plain filing. I looked at the screenshots.
- Every number on every card was compared with the filing during development (Reliance, Kaynes, Bajaj Finance, Tata Steel, ITC) and with Yahoo.

**Issues found and fixed:**
- ITC prints its year-ago column second: the order is now read from the header dates.
- ITC's own PDF has a damaged profit row (a figure stuck in the label, a "B" for an "8"): recomputed as PBT less tax only because the printed column confirms the sum, and labelled as computed.
- A scanned filing parses garbage digits as numbers; it now shows a figure only where Yahoo agrees.
- "Mr." and "w.e.f." were treated as ends of sentences, which cut HDFC's profile to a fragment.
- A profile section ran into the next person's heading, so one appointee would have been shown another's profile. The two-appointee test caught it before it shipped.
- A case-insensitive pattern read "has" as part of a name ("Mr. A. Kumar has").
- A role ran on into the next sentence after "Ms." and hid the DIN.
- Two regexes had lost their `\b` to a backspace character (the second time this class of bug has happened); a test now forbids control characters in source.
- The classifier called Tata Steel's Vice-Chairman "a minor role" because "Non-Independent Director" contains "independent director".

**Not built yet:** a web-search bio (needs search and model keys, and the filing's own profile already answers it); a model-written summary of the other categories. No model is used anywhere yet, so the cost log is still empty.

**Limits:** the profile shown is the first sentences of what the company chose to file, so it is the company's own description, not an independent one. A filing whose reading order is scrambled (a scan) may yield only part of the facts, and says so. Yahoo's quarterly data lags a fresh filing by days.

## Step 9: The Pull engine (2026-11-15)

**Asked:** read a company's primary documents (concall transcripts and the annual report), build the Promise Tracker (what was promised on the last four calls and whether later calls show it was kept), answer questions only from those documents, and make it work for a ticker that was never prepared in advance.

**Done:**
- **Documents:** finds the last four concall transcripts (one per quarter) and the latest annual report on BSE, or on NSE for a company BSE does not list; downloads them through the safe fetch (allow-list, 25 MB cap); reads their text; keeps each file's pages in the cache so it is fetched once.
- **Chunks and statements:** each chunk keeps its page; a speaker's label starts a new chunk; what management said about the future is found by rule (no model), word for word with its page.
- **Retrieval:** BM25 in plain Python. It decides "Not found in the documents" before any model is asked.
- **Promise Tracker and Ask:** the prompts, the checks and the scorecard are built and tested with a scripted model. Every quote must be word for word on its page, a verdict needs a later quote, the counts are computed in code, and an answer's figures must appear in its quotes.
- **Model router:** Gemini and Groq over REST, three tiers, backoff and fallback, a cache, a usage log and a report command. **Not run against a live model: there are no API keys.**
- **Serving:** `GET/POST /research/{ticker}` (a finished record, a job's stage, or a reason), `POST /ask`; background jobs; a daily cap on fresh work; per-endpoint rate limits with a global ceiling; the demo companies' documents ship with the backend.
- **Precompute:** `python -m pipeline.research` for the four research companies.

**Real data:** Bajaj Finance, Asian Paints, HAL and Info Edge read from the live exchanges in about three minutes: 16 transcripts and 3 annual reports (Asian Paints' is over the 25 MB limit and was skipped, with a warning), 4 to 24 rule-found statements each. **A ticker that was never prepared (Titan) was researched live through the local engine**: 4 transcripts and a 473-page annual report, 7 statements. It was then asked about: passages with their pages, "Not found in the documents" for an unrelated question, and a 409 for a company that had not been researched.

**Verified:**
- Backend 562 tests (was 389): the router against a fake transport (requests, backoff, fallback, cache, log, no key in any line), real transcripts through chunking, statements and retrieval (every statement is a verbatim span of its page), ingestion with every failure path, the Promise Tracker's checks, Ask's three outcomes, the engine and routes (jobs, the cap, rate limits, no stack traces), and the corpus store.

**Issues found and fixed:**
- Asian Paints' calls were mislabelled: a date in the filing's text (the call's) was read as a quarter-end, so the January call became "Q4", the May call "Q1 FY27", and the real Q4 call was lost in de-duplication. Labels now come from explicit text, else the quarter that ended before the call.
- The annual report picked was a 2-page covering letter; it is now the biggest filing of the latest cycle, with a 20-page minimum.
- The rate limit could be dodged by changing the ticker (slowapi counts per URL), and its middleware cannot see routes in a router. Every route now states its own limits.
- A "passage" shown for a question joined sentences that were not adjacent on the page, so it was not word for word. It is now always a run of adjacent sentences.
- Real transcripts leave management's answers unlabelled, so showing the last speaker's name would have misattributed them. Speakers are not shown.
- Analysts' remarks ("my question is on...", "that you mentioned...") and agencies' forecasts were listed as management's promises; they are filtered.
- An annual report's title said FY27 for the FY26 report.

**Not built yet:** the promise verdicts and written answers need a model key (`GEMINI_API_KEY` and `LLM_CHEAP_MODEL` in `.env`, then `python -m pipeline.research`). A Tavily search is not used at all. HAL files only one transcript, so no tracker is possible for it.

**Limits:** BSE and NSE are only proven reachable from a home connection, so an unseen ticker on a deployed server may fail with a stated reason, while the four prepared companies do not depend on it. The daily cap resets when a free instance restarts.

## Step 10: The Research screen (2026-11-15)

**Asked:** a screen for the scorecard, quotes with their document and page, and "Ask the documents"; every claim must lead to its source.

**Done:** the Research tab: a ticker box (validated the way the engine validates it) and the companies ready to read. For a company, the verdict first (the scorecard, then the promises, bad news first, with evidence on demand), then what management said about the future, a box to ask the documents, the documents read (with links), and what could not be read. Every quote has "Open at that page" (the PDF opened at that page where the browser allows it). There is a state for each way a lookup can go: a record with no verdicts ("No verdict yet"), an engine that is waking up, work in progress with its stage, a failure, the day's allowance spent, an engine that is offline, and one that is not connected.

**Verified:** 71 frontend unit tests (the flow that fetches, wakes, starts and polls, with a fake clock); lint, type-check and production build. 11 checks in a real phone-sized Chromium against the real local engine and the real data: the tab and the ticker form; a bad ticker refused where it is typed; a prepared company opening at once with 11 quotes and 11 page links; every quote on screen matching the engine's own record; Ask returning passages and "Not found in the documents"; a question that is too short refused without a request; a sleeping engine described as asleep; an unprepared company followed through its stages to its record; a record with verdicts (bad news first, evidence on demand, counts as calculated); no overflow at 390 px with 44 px tap targets, in light and dark; and an invalid ticker in the address. I looked at the screenshots.

**Limits:** the verdict view was exercised with a hand-built record because no model has run; its own text says what each part is. The browser opens a PDF at the page only where its viewer honours `#page=`.

## Step 11: Polish, documentation and the submission pack (2026-11-15)

**Asked:** a 390 px phone pass, then the README, an architecture diagram, the cost table, a write-up and the build history, so the submission email is ready.

**Done:**
- **Phone pass.** Every screen was captured at 390 px on the production build with real data, in light and dark, and looked at: Brief, results and management cards, Alerts, Research home, a company's research, Settings. One wording fix (the Research list said "Documents read" twice). No overflow, no console errors, contrast good in dark.
- **README** rewritten: what it does, a table of what is verified and what is not, how it avoids making things up, the architecture diagram, cost and efficiency, how to run, where things are. Seven screenshots in `docs/screens/`.
- **Architecture** doc with the final diagram, the three flows (push, pull prepared in advance, pull on demand) and how the pieces are kept honest.
- **Write-up** (`docs/write-up.md`): the approach, the decisions that mattered, and what to do next.
- **Submission pack** (`docs/submission.md`): a checklist of what only the owner can do (keys, the first real verdicts, deploy, the Render check) and the email, with the places to fill in marked. `docs/deploy.md` gained the steps to turn on the Promise Tracker and a smoke test after deploying.

**Verified:**
- Backend 564 tests, frontend 71 unit tests, type-check, lint, production build, secret scan.
- All earlier browser checks re-run on the **production build**: the Brief 11/11, Alerts and Settings 9/9, the cards 17/17, Research 11/11. The Step 2 skeleton check "A" is retired: it hard-codes the skeleton's sample timestamp and "Sample data" label, which real data replaced in Step 4. Built with `NEXT_PUBLIC_API_URL` set, as it will be on Vercel; without it the pill correctly says "Engine not configured".
- **Memory on a free instance:** the API idles at 63 MB. A cold research of a company never fetched before (Pidilite: four transcripts and an 11.5 MB, 338-page annual report) took 8 seconds and peaked at 131 MB, against Render's 512 MB.

**Issues found and fixed:**
- Two simultaneous requests for one ticker could each start a job and count the daily cap twice. Now under a lock; the test would fail without it (8 jobs, 7 counts).
- A blank line copied from `.env.example` ("RATE_LIMIT_DEFAULT=") gave an empty limit string that broke the limiter; blank now means "not set".
- The deploy guide still described the skeleton's "Sample data" tag.

**Not done, and why:** deployment to Vercel and Render, the API keys and the first real run of the model path need the owner's accounts; the checklist is in `docs/submission.md`.

## First live run of the model path (15 Nov 2026)

**Asked:** put the Gemini key in use, pick the free Flash-Lite and Flash models, build the Promise Tracker for the four research companies, refresh the Brief data, measure cost.

**Done:** `LLM_CHEAP_MODEL=gemini-3.5-flash-lite`, `LLM_STRONG_MODEL=gemini-3.5-flash` (both answered a test call; `gemini-2.5-*` return 404 "no longer available to new users"; `gemini-3.8-flash` listed but timed out twice). Promise Tracker built for Bajaj Finance, Asian Paints, Naukri (54 verdicts: 24 Kept, 3 Partly, 0 Missed, 27 Too early); HAL has one call in the window, so statements only. Portfolio data refreshed for 18 companies. Measured cost in [cost.md](cost.md).

**Issues:** (1) the key had been pasted into the tracked `.env.example` instead of `.env`; moved it to the gitignored `.env` and restored the example before any commit. (2) 4 strong-model verdict calls were cut off at the token limit because Gemini 3.x thinking tokens count against the output cap; fixed with `thinkingLevel: low` and a higher cap, thinking tokens now counted. No prompt was changed. (3) No verdict is Missed: the spot check found them reasonable but at times generous (for example "more than 9 lakh trained" against a goal of "almost 10 lakh" is Kept).

## Honest Promise Tracker (15 Nov 2026, second live run)

**Asked:** the first live run was too generous (54 verdicts: 24 Kept, 3 Partly, 0 Missed, 27 Too early). "Too early" only when the promise's date is after the latest call, decided by code; a new "Not followed up" verdict; a rubric where numbers decide; search every later call; re-run and read the verdicts against the transcripts.

**Done:**
- `app/pull/periods.py` reads a time frame ("Q3 FY27", "second half", "by September '26", "within a year's time") to the last day of the period on the Indian fiscal calendar, relative to the day of the call. `resolve_due` reads the quote and the speaker's own words first and the model's `target_period` last: the model read "this year", said in Feb 2026, as FY27 and "first half of this year" as H2.
- Verdicts: Kept / Partly / Missed (or "Missed, delayed" when management pushed it back) / Not followed up / Too early. Kept, Partly and Missed only once the date has passed, except management's own words that it has slipped. The judge returns an outcome plus `target_value` / `actual_value`; code checks both numbers are in the quotes and decides: met = Kept, 75-99% = Partly, below 75% = Missed.
- Every later call is searched on its own (BM25), also with the sentences said just before the commitment (they name the subject), one commitment per model call, with the passage it was said in. A verdict decided by words is read a second time ("same subject? supports it?"); one that does not pass is shown as Not followed up. A miss needs a word of a miss in the quote it cites.
- Router: a model whose free daily quota is gone is skipped for an hour, not retried; Gemini's own `retryDelay` is honoured.
- Frontend: five statuses (amber for Not followed up), a legend, the due date, the numbers behind a verdict, "as of the latest call".

**Verified:** backend 680 tests, frontend 73, type-check, lint. Live: 3 companies, 40 promises: 5 Kept, 1 Partly, 1 Missed, 4 Not followed up, 29 Too early. Read against the transcripts: Asian Paints "almost 10 lakh" vs "more than 9 lakh" is now Partly (90%); Bajaj "wind down below INR 1,500 crore by Sept '26" vs "now down to INR 2,400 crore" is Missed (62.5%); the VAE facility "started in September" is Kept; Bajaj's B2B AI model is Kept. "Ask the documents" run live on all four companies.

**Issues found and fixed on the way:** the number reader rejected "INR2,400" (so the Bajaj miss was Kept on the model's word); the retrieval needed two shared words, which hid the one passage that said "we started our VAE facility", and "VAM-VAE" never matched "VAM and VAE"; a judge asked about several commitments at once cited a B2C quote for a B2B promise and a quote about EXPANDING to 18 cities as proof of a postponement.

**Not working:** Naukri "billings growth to recover in Q1" (about 99acres) is shown as Not followed up, which is wrong: the Q1 call discusses 99acres billings and the search did not surface that passage. The strong model's free quota is 20 requests a day and was used up by re-runs, so every verdict in these records was made by `gemini-3.5-flash-lite` (the record says so). Re-running after the quota resets would use the strong model.

## Deploy (15 Nov 2026)

**Asked:** deploy on free tiers, wire CORS, check from the command line, fill the Render column of the data-source table, remove the debug route, finish the docs and the email.

**Done:**
- **Render** (free plan, Singapore), created through Render's API from `render.yaml`'s settings: https://finn-api-v8fm.onrender.com. Env vars set from `.env` (Gemini key, model names, `ADMIN_TOKEN` generated, daily cap 20, `ALLOWED_ORIGINS` = the Vercel origin). Empty keys (Groq, Tavily, fallback model) were left unset.
- **Vercel** (Hobby): https://finn-mocha.vercel.app, project `finn`, `NEXT_PUBLIC_API_URL` = the Render URL for production, deployed with the CLI from `frontend/`. A `.vercelignore` keeps `.env*` and a stray untracked `public/pub.env.local` out of the upload (the file is not served: 404).
- **Checks from the command line:** the Vercel URL answers 200 and its JavaScript contains the Render URL; `/health` on Render answers; a CORS preflight and a GET from the Vercel origin return `access-control-allow-origin: https://finn-mocha.vercel.app`, and a foreign origin gets no such header; `/debug/sources` answers 404 (removed); "Ask the documents" answered from the deployed backend with four quotes.
- **Section E (what the exchanges allow from Render):** Yahoo, NSE announcements and screener.in work; **BSE answers HTTP 403** on every endpoint. Result in `docs/data-sources.md`. The debug route and `backend/probes/` were then removed.
- **TITAN (never prepared) on Render:** fails in 8 seconds with "The research could not be completed (FetchError)", because the BSE scrip list is refused. A stated reason, not a crash. The four prepared companies do not depend on it.

**Not done, and why:**
- Neither platform deploys on `git push`. Render: a service created through the API from a public repo has no GitHub webhook, so I trigger deploys through the API. Vercel: `vercel git connect` fails because the Vercel account has no GitHub login linked (needs a click in the browser).
- An unprepared ticker does not work from Render (BSE 403). The next step is to let the engine resolve a company from NSE alone.

## Evening polish (15 Nov 2026): look and feel, a concept preview, two fixes

**Asked:** four phases, each its own commit and deploy: (1) visual clarity, (2) a concept preview of personalisation, (3) the wrong Naukri verdict, (4) live research on Render.

**Done:**
- **Phase 1** (`998a37f`): the pipeline keeps 30 price sessions per company (data refreshed for 22 companies). A price chip (latest complete session, coloured move, day of the close) and a 30-day sparkline on every card in the Brief, Alerts and the Research header; initials avatars with a colour fixed by the symbol; one line icon per category; revenue and profit bar groups on results cards; a stacked verdict bar on Research with a legend; the time window moved into a bottom sheet behind a sliders button, with "Today's Highlights" / "Highlights: last N days"; headlines lead with the company's short name. Everything is inline SVG. The Brief's priority groups, risk-first order, collapsed routine row and "You're all caught up" are unchanged. `scripts/shoot.py` takes phone-width screenshots (real mobile emulation, light and dark).
- **Phase 2** (`26d4ea6`): the Brief has two swipeable tabs, Invested (unchanged) and Interested (the research companies with real prices and verdict bars, a Follow star, an Invest button that opens a "coming soon" sheet) and "People to follow" from real management-change filings. All frontend, all marked Preview; following is stored in the browser only. Decisions S85-S95 and the notes on where to take it in `docs/write-up.md`.
- **Phase 3** (`3eee32f`): Naukri's "billings growth to recover in Q1" is about 99acres, named two sentences before the quote. Retrieval now also searches the names found in those sentences among the chunks of each later call that name them. Re-run for Naukri only: the verdict changed from the wrong "Not followed up" to Kept, with "Billings grew by 21% YoY in Q2, up from 17% in Q1" (99acres, Q2 call, p5).
- **Phase 4** (`0bc518d`): BSE answers 403 to Render, and the company index needed BSE's scrip master, so an unprepared ticker died at "Finding the company". The index is now NSE-only when BSE refuses. TITAN on the deployed backend: four transcripts read from NSE's archives, 6 promises, 32 seconds; Ask answered with two quotes. No annual report was in NSE's feed, and the record says so.

**Verified:** 678 backend tests, 89 frontend tests, type-check, lint, secret check; each phase deployed and looked at on the live site at 390 px (light and dark); the live page shows "Engine online". README screenshots retaken from the live site (`scripts/readme_shots.sh`).

**Issues found on the way:** the headless browser's minimum window width made the first captures a false 390 px (fixed with real device emulation); a tab swipe could flip the selected tab mid-animation (it now settles on the tapped tab); the first Naukri re-run still said "Not followed up" until the lead-in search was added (it needed a name search, not more excerpts).

**Not working / known:** most shipped verdicts were made by the cheap model because the strong model's free daily quota ran out. Neither Vercel nor Render deploys on push. A few verdicts may be wrong in the ways described above; they are not audited line by line.

## Phone fix and a calmer Brief (15 Nov 2026)

**Asked:** fix the Brief being wider than a real 360 px phone; 3-line cards grouped by company; short category labels; then from user testing: a greeting, short "why" lines, one window control for Brief and Alerts, new background colours, and a profile-feel "You" tab.

**Done:**
- **The overflow, and its real cause.** Not the card header. The screen-reader text in the price chip (`sr-only`, absolutely positioned) inside the off-screen Interested tab escaped the tab scroller's clip, because the scroller was not a positioned element. It sat at x = 558 and stretched the document to 558 px; Android Chrome then widened the layout viewport, so the fixed nav (430 px wide) landed at `left: 64` with a dark strip on the right. Reproduced on the live site first (`html.scrollWidth` 558 at 360 px). Fixed at the cause (the scroller is `relative`), with a safety net (the layout column is `relative` and `overflow-x: clip`, and so is `body`). The bottom nav is now a `sticky` child of that same centred column, so it always has the column's width and position.
- **3-line cards, grouped by company.** One company header (badge, short name, price chip `₹3,430.00 ▼ 1.55%`), then each filing under it as a bold headline and one grey line (icon, short label, short reason, tone). Sparkline, time, results table, profile, PDF link, full reason and Mute are behind the tap. Companies are ordered by their highest-priority filing; the Alerts tab uses the same card. Short labels: Results, M&A, People, Fund raise, Legal, Rating, Dividend, Pledge, Meeting, Routine (plus Bonus, Capex, Update, Other for the rest). The Interested rows use the same three lines (Promise Tracker counts, bad news first, tone by fixed rule on the counts).
- **From user testing:** the greeting ("Good evening · Sun, 15 Nov", with the name if given) from the device clock; a short "why" of about eight words, built by rules from the card's figures or the pipeline's own note ("Profit fell vs last year"), the long reason kept in the details; one `WindowHeader` component (sliders button, bottom sheet, "Showing the last 24 hours") on both Brief and Alerts, one stored setting; soft indigo-tinted charcoal page with lighter cards in dark, warm off-white page with white cards in light, every text pairing checked at 4.5:1 or better (two tokens adjusted to get there); the Settings tab is now **You** (profile circle, optional name in localStorage, My portfolio with mute, Preferences, How FINN works, "No account needed").

**Verified:** 112 frontend unit tests (new: grouping and order, labels, short why, headlines, greeting, name, scorecard wording), type-check, lint, production build. In a real phone-sized Chromium on the production build: Brief, Interested, Alerts and You at 360 and 390 px, light and dark, collapsed and fully expanded: `scrollWidth` equals `clientWidth`, the nav is at left 0 with the screen's width, and no text is below 4.5:1 contrast. 29 behaviour checks (shared window setting across screens, name typing and greeting, nav pinned while scrolling).

**Not working / known:** the Language row on You is honest, not a setting (English is the only language). A headline can take two lines (not one) so it is not cut mid-fact. The "Signal" cards on Alerts (price and volume) keep their older layout. Vitest fails to start from this Git Bash session (a worker error on every file, also on a clean checkout) but passes from PowerShell; the cause was not found and it is unrelated to the code.

## Calm colours, summary line, calm alerts (15 Nov 2026, "Chat 2" of the night's prompts)

**Asked:** an indigo accent with softer status colours; one summary line computed in code; calm alerts (a dot not a number, a plain reason on every alert, whether a filing explains a price or volume move); the You tab. The You tab, the shared window sheet, the greeting and the new backgrounds were already in `12afdab`.

**Done:**
- **Accent:** deep indigo (`--accent`, `--accent-bg`, `--on-accent`) for the active tab and nav item, buttons, links, switches, sliders and one focus ring everywhere; never used for good or bad. Red and its tint made richer; green and amber unchanged. Every text pairing is at 4.5:1 or better, light and dark.
- **Summary line** (`summaryParts` in `lib/brief.ts`, unit-tested): "N risks to review" (material filings tagged Risk) and "Busy day: N of your companies filed" (five or more companies with a material filing), joined with " · "; "Quiet day: nothing needs action across your 18 companies" when nothing is material. Where something is material but is neither a risk nor a busy day it says "N filings worth a look" (not in the brief; a fallback so the line is never empty). It replaces "N things that matter".
- **Alerts:** the tab shows a small indigo dot, no number, when there are alerts and the reader has not opened Alerts since the data was refreshed (`lib/alertsSeen.ts`, localStorage). The header says "N material alerts". Every price or volume alert states its reason against the reader's own limit ("Price −6.1% · your limit ±5%", "Volume 3.2× the 20-day average · your limit 2×") and whether a filing explains it: the company's material (not routine) filing of the same India calendar day, named by its short label, else "No filing explains this move". Real data only; for an older session it says "that day", not "today".

**Verified:** 120 unit tests, types, lint, build; Brief, Alerts, You and Research at 360 and 390 px, light and dark, no sideways scroll and no text below 4.5:1; 29 behaviour checks.

**Not done:** the dot's "new" is per data refresh, not per alert (there is no per-alert read state).

## Research redesign: verdict summary, bad-news-first promises (15 Nov 2026, "Chat R")

**Asked:** make the Research screens calm, scannable and convincing; ENAM values "promised vs delivered" most. Frontend only, real data only, every quote word for word with its page.

**Done:**
- **Company page**, top to bottom: header (badge, name, price chip, then "4 calls + annual report read · updated 15 Nov 2026"); a verdict summary computed in code (`Delivered 2 of 5 promises that came due`, a stacked bar led by Missed, one plain "so what" line from fixed rules, "Verdicts by gemini-3.5-flash-lite, checked against later calls"); promises in bad-news-first groups (Missed, Not followed up, Partly, Kept; five per group, then "Show more"), each a three-line card: verdict chip and a 2-4 word topic cut from the promise's own words, a word-for-word excerpt of at most 80 characters, and "Said in Q3 FY26 call → checked in Q2 FY27 call"; tap for the full quote with "Open at page N", what a later call says, the numbers and the reason. "Too early" promises are one collapsed row ("15 promises are due later"), soonest due first. What management said about the future is collapsed, newest call first, three per call. Ask the documents has three example chips. A company with fewer than two calls (HAL) gets a calm explanation card instead of a fake verdict.
- **Research home:** each company is three lines (badge, name, price chip; "Delivered 5 of 7 due" with a thin bar, or "Not enough calls yet"; "4 calls + annual report read · updated ...").
- **Rules, all in `lib/research.ts` and unit-tested:** delivered = Kept + Partly out of Kept, Partly, Missed and Not followed up (Too early is not counted); the "so what" line; the topic and the excerpt (a prefix of the quote, never reworded).

**Verified:** 129 unit tests, types, lint, build. In a phone-sized Chromium: 36 behaviour checks on the real shipped records (the summary numbers recomputed from the raw record, group order, at most five per group, every excerpt on screen is the unchanged start of a real quote, three lines per collapsed card, page links of the form `.pdf#page=N`, collapsed rows, HAL's explanation, the Interested-tab link into Research); 360 and 390 px, light and dark, no sideways scroll and no text below 4.5:1.

**Not working / known:** the topic is cut by rules, so a few are clumsy ("Run off the specific"). The excerpt is the start of the quote, not the most telling part. The HAL card says "found", not "in the last 12 months", because the engine looked back 14 months. Verdicts on shipped companies were made by the cheap model (the strong model's free quota ran out earlier). Ask needs the live engine; with it asleep it says so.

## Final docs and live checks (15 Nov 2026, "Chat 4")

**Asked:** the research references, the README and write-up sections the email needs, one live TITAN run, a Naukri re-check, fresh README screenshots, and the email text.

**Done:**
- **References checked before use.** Each number was searched: 9.5% fewer logins after a market decline (Sicherman et al., RFS 29(4)) and 93% of 2,455 alerts overridden in four days (Bryant, Fletcher & Payne, 2014) are right. **The 73.3% (Nanji et al., JAMIA 2018) is an inpatient study at a 793-bed hospital, not outpatient**, so it is cited as that. The Groww claim is press commentary and is labelled so. Only the references in the brief are used.
- **TITAN on the deployed engine:** it woke at once, researched TITAN in 34 seconds (four transcripts of 18 to 19 pages; 8 promises, 1 Not followed up and 7 Too early; 7 statements; the cheap model, 9 calls, about 21,000 tokens in), answered "What did management say about margins?" with four quotes, and answered an unrelated question with "Not found in the documents". No annual report was in NSE's feed ("No annual report was found among the filings of the last 14 months"), and the record says so.
- **Naukri, re-read from the live site:** the 99acres billings promise is **Kept**, with "Billings grew by 21% YoY in Q2, up from 17% in Q1" from the Q2 FY27 call, page 5. It was the wrong "Not followed up".
- **Tests:** 680 backend tests pass; 129 frontend unit tests, types, lint and build pass.

**Not working / known:** see the Known limits in `docs/submission.md`.


**Late addition, found by looking at the TITAN page:** "Delivered 0 of 1 promises that came due" followed by a so-what line reads as a verdict on a record of one. When fewer than three promises have come due the line now says "Only 1 promise has come due, too few to judge" (decision S107). Deployed and checked on the live site: 36 of 36 Research checks, 29 of 29 earlier checks, no sideways scroll and no text below 4.5:1 on the TITAN page. The README screenshots were retaken from the live site at 390 px.

## My money, the What if calculator, the mark (16 Nov 2026)

**Asked:** the engine wake-up (P0), My investments with the mute toggles reversed (P1), a "What if" calculator (P2), the FINN mark (P3).

**Done:** P0 (`01b66e6`), P1 (`4b8a44f`) and the mark (`70ee29f`) shipped earlier. The calculator is one component in an open Brief card and on every Research page, with its arithmetic in `lib/whatif.ts` (12 unit tests: gains, losses, 0%, an empty box, ₹1 lakh crore, a history too short, a bar still being traded). Today's row is the latest session's change; "Last 30 days" is the latest close against the close on or before 30 calendar days earlier (the data keeps 30 sessions, about 44 days), left out if the history is too short. Decisions S111 to S115.

**Verified:** 148 unit tests, types, lint, build. 24 checks in a phone-sized browser on the real data (the 30-day figure recomputed independently in Python from the raw prices, Indian grouping, validation of a bad, negative and empty amount, the slider spoken as "minus 10 percent, you'd have 9,000 rupees", keyboard steps of 1%, every tap target 44 px, the amount prefilled from My investments, the calculator under the header on Research and absent from a collapsed card); 360 and 390 px, light and dark, every card open: no sideways scroll, no text below 4.5:1.

**Not done:** the soft section boxes from P3. The calculator restates the past; it forecasts nothing.

