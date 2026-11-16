# Night report: FINN, 16 Nov 2026

**Live:** https://finn-mocha.vercel.app (shows "Engine online"). **Code deployed:** Vercel is on `c0fa243` (frontend) and Render on `5dec625` (engine); the docs commit after them is `bde3c16` (it changes no app code, so nothing needed redeploying). **Data:** made 16 Nov 2026, 06:05 IST, 22 companies, no problems.

## Done, skipped, reverted

| Part | Result | Commit |
|---|---|---|
| 0 Calculator on `main` | Already there before the night began (checked, not redone). | `6817142` |
| A My portfolio, profit and loss | **Done.** Amount plus optional buy price; profit and loss only with a buy price, never a made-up one; portfolio card (invested, worth now, overall, today) with a breakdown, biggest loss first; the Brief header shows "overall" only with a buy price; "Try with sample holdings" (labelled, asks before replacing, Clear). 26 new unit tests. | `7dba308` |
| B Follow companies, people, topics | **Done.** `research_brief.json` (filings of the research companies, same shape, separate file); search box, chips, Following feed in the Brief's cards with "Because you follow ...", honest empty states; 25 unit tests; Preview badge removed from following, kept on Invest. | `00420c9` |
| C Polish | **Done.** Soft section boxes (they did not break the layout); stale You-tab check replaced by one that looks for the four sections by id (the old one was never in the repo); plain-word reasons ("Company news" became "Company update"). | `1b6f6f7` |
| D Ready for graders | **Done, except Lighthouse (see Skipped).** Stale-data safety ("Latest highlights", "Data as of", an honest footer); a quiet 24 hours now looks further back and says so; first-visit hint; 60-second demo in the README and the email; speed work. | `2ee267c` |
| E Good and bad as tints | **Done.** Soft tints with a 3px edge and a word or arrow beside the colour, on every card type; checked at the exact mix in light and dark; two dark-mode contrast failures found by the checker and fixed. | `62eae37` |
| F Refresh, docs, final checks | **Done.** Fresh data (`46ee3d3`); three console 404s found by walking the demo live and fixed (`c0fa243` in the app, `5dec625` on the engine); README, write-up, decisions, email, build log. | `46ee3d3`, `c0fa243`, `5dec625`, `bde3c16` |

**Skipped:** Lighthouse. The environment refused to download and run it (`npx lighthouse`) and I did not work around that. I wrote `scripts/perf_audit.py` instead, which measures the same things in a real Chromium on the live site with Lighthouse's mobile settings. The README says plainly that these are not Lighthouse scores.
**Reverted:** nothing. No earlier work was removed. Everything is in `docs/decisions.md` (S116 to S137).

## Live check results

- **Browser sweep** (`scripts/check_live.py`, real phone-sized Chromium, the live site, after the last deploy): **582 of 583** checks passed (the one that failed was the engine answering 404 for a ticker nobody had researched; it now answers 200, Render was redeployed, and those scenarios were re-run: 58 of 58). Every screen and state at 360 and 390 px, light and dark: no console or network error, no sideways scroll, every text at 4.5:1 or better, and per-feature assertions. The checker was itself tested against a faked overflow and a faked low-contrast element.
- **60-second demo** (`scripts/live_demo.py`): **18 of 18**: Kaynes results card; Figures as printed with a link to the filing at that page; Bajaj Finance, misses first; Ask answered "What did they say about margins?" with quotes and pages; TITAN researched live (57 seconds from a cold engine) with no console error from any step; sample holdings, the portfolio card and the calculator. "Engine online" showed.
- **Tests:** 683 backend, 213 frontend unit tests; type-check, lint and production build clean; the secret check clean on every commit.
- **Speed** (`scripts/perf_audit.py`, live, median of 5, slow 4G and a 4x slower CPU; not Lighthouse):

| Page | First paint | Largest paint | Layout shift | Blocking time |
|---|---|---|---|---|
| Brief | 0.70 s | 1.63 s | 0.001 | 0 ms |
| Alerts | 0.66 s | 1.55 s | 0.001 | 0 ms |
| Research | 0.61 s | 1.50 s | 0.041 | 0 ms |
| You | 0.65 s | 1.56 s | 0.001 | 0 ms |

  All are inside Lighthouse's "good" limits. Before tonight's fixes Alerts took 4.6 s to its largest paint on the live site.
- **Found only because the checks looked at real output:** the weekend-data Brief opened on "Quiet day" with the Kaynes card three days back (now it looks further back and says so); amber "Preview" text on an indigo button at 1.4:1; "Risk" on a tinted card at 3.9:1 in dark mode; a heading sentence that made the page jump (layout shift 0.093, now 0.001); three console 404s when researching a ticker that was never prepared (two in the app, one from the engine).

## Known problems, stated plainly

1. **Lighthouse was not run** (above). Run `npx lighthouse https://finn-mocha.vercel.app --form-factor=mobile --view` yourself if you want the official scores.
2. **Not tested on a real phone**, only in a phone-sized Chromium at 360 and 390 px.
3. **Following is exact-match.** A person is found by their exact full name, so "Mr. V. S. Rangan" in a filing will not match "V. Srinivasa Rangan"; a topic's keyword rule can miss an unusual wording. It covers the 22 tracked companies only, and sends no push notification.
4. **The Brief can show "today" when it is not today.** Until a reader picks a window, a quiet 24 hours looks back to 3 or 7 days (it says so under the summary line). If you would rather have the strict 24 hours, it is one function, `effectiveWindow` in `frontend/lib/brief.ts`.
5. **The data is from Monday 06:05 IST and nothing had been filed since Sunday 22:05.** If a grader opens it days later the page says "Latest highlights" and "Data as of". The data is not refreshed on a schedule (no server can reach BSE); I run `pipeline.run` by hand.
6. **The research engine is on a free server.** The first Research or Ask action after it sleeps can take up to 2 minutes (the page says so). I used a few of the daily fresh-research allowance tonight (TITAN several times).
7. **From earlier, unchanged:** Promise Tracker verdicts were read against transcripts but not all audited; most were made by the cheap model because the strong model's free quota ran out; HAL has one call so it has no tracker.
8. `frontend/public/pub.env.local` is an untracked file that was there before tonight (it holds only the public API URL; `.vercelignore` keeps it out of the deploy). I left it alone. The plan file is now `docs/FINAL-NIGHT-PLAN.md`.

## EMAIL LINES

Paste these into the email (they are the same text as in `docs/submission.md`, which also has the rest of the email).

### 60-second demo

**60-second demo** (open https://finn-mocha.vercel.app on a phone; the research engine is on a free server, so the first Research action may take up to 2 minutes to wake)
1. **Brief:** open the Kaynes results card.
2. Tap **Figures as printed** to see the source page.
3. **Research → Bajaj Finance:** promises, misses first.
4. Ask **"What did they say about margins?"**
5. **Research TITAN** (never prepared; wakes the free server, up to 2 min).
6. **You → "Try with sample holdings"**, then open a card on the Brief for the calculator.


### What I built

- **Push:** a Morning Brief of 18 portfolio companies. One line counted in code ("1 risk to review", "Busy day: 6 of your companies filed", or "Quiet day"), then each company once with its filings under it in three lines, ranked so risks come first, with routine filings collapsed and a finite end. Good and bad are soft tints with a word or arrow beside the colour. Results cards (Revenue, EBITDA, PBT, PAT, QoQ and YoY, read from the filing with no model and checked against Yahoo Finance); management-change cards with the filing's own profile; calm alerts on thresholds the user sets, each stating its reason and whether a same-day filing explains the move. Old data says it is old ("Latest highlights", "Data as of"), and on a quiet day the Brief looks further back and says so.
- **Pull:** research on any NSE ticker from the company's own transcripts and annual report: "Delivered 2 of 5 promises that came due" counted in code, a Promise Tracker with the bad news first (Kept / Partly / Missed / Not followed up / Too early, each with its quote, document and page), what management said about the future, and "Ask the documents", which answers only from the filings or says "Not found in the documents".
- **You:** a profile with no account (an optional name kept on the phone), the portfolio with "Show in my brief" switches, My investments, preferences, and how FINN works.
- **My money, in rupees:** optional amounts and average buy prices per company (kept on the phone only) give profit and loss: a portfolio card on the Brief (invested, worth now, overall, today, with a breakdown, biggest loss first) and "Your ₹50,000 · ▼ ₹775 today · ▲ ₹4,200 overall" on each company. Without a buy price it shows only today's move, never an invented profit. "Try with sample holdings" fills clearly labelled sample numbers. A **What if** calculator in each open card and at the top of every Research page restates real moves in rupees (today, the last 30 days, and a slider from −20% to +20%). It predicts nothing and says it is not advice.
- **Follow:** one search box follows a company, a person (by exact full name) or one of ten topics, and a Following feed shows the matching filings in the Brief's own cards, each with "Because you follow ...". It covers the 22 companies FINN tracks, reads filings (not news) and sends no push notification.

### Where I'd take it next

- Rank the Brief by exposure to what each reader holds (the amounts are already kept on the phone).
- Follow any NSE company, not only the 22, and follow a person through insider trades, substantial acquisitions (SAST) and management changes.
- A three-question first-time setup; one brief a day with quiet hours.
- Hinglish across the app.
- Investing through a SEBI-registered broker partner, as the revenue model.

### Known limits

1. The Promise Tracker's first run was too generous (24 of 54 verdicts Kept), so dates and numbers are now decided by code and a second reading was added. It is now 40 promises: 6 Kept, 1 Partly, 1 Missed, 3 Not followed up, 29 Too early. I read each decided verdict against its transcript and fixed what I found, but have not audited all of them.
2. The strong model's free quota (20 requests a day) ran out during re-runs, so most verdicts were made by the cheap model, `gemini-3.5-flash-lite`; each record says which model answered.
3. Naukri's 99acres billings promise was wrongly "Not followed up"; it is now Kept, with the Q2 FY27 call (page 5) as evidence, re-read on the live site.
4. A ticker I never prepared works live: TITAN was researched on the deployed engine in 34 seconds (four transcripts, 8 promises, a question answered with quotes, an unrelated one answered "Not found"). BSE answers HTTP 403 from Render, so the engine falls back to NSE, whose feed had no annual report for TITAN; the record says so.
5. HAL has only one call, so it has no tracker (the page says why); Asian Paints' annual report is over the 25 MB limit and is skipped.
6. Invest is a concept (a "coming soon" sheet). Following matches filings by exact name and by category or keywords, so a different spelling of a name will not match; it sends no push notifications.
7. Checked in a phone-sized browser at 360 and 390 px, light and dark, not on a real phone: 582 of 583 scripted checks passed on the live site in the last full run, and the one that failed (the engine answering 404 for a ticker nobody had researched) was fixed and its scenarios re-run, 58 of 58. Neither Vercel nor Render deploys on push; I deploy by hand.
8. I could not run Lighthouse (my environment would not let me download and run it). `scripts/perf_audit.py` measures first and largest paint, layout shift, blocking time and accessibility checks on the live site with Lighthouse's mobile settings, and they are inside its "good" limits, but they are my measurements, not Lighthouse scores. `npx lighthouse https://finn-mocha.vercel.app --form-factor=mobile` gives the official ones.

## MORNING CHECKLIST

1. Open https://finn-mocha.vercel.app on your phone and do the 60-second demo (the first Research action may take up to 2 minutes to wake the server).
2. Put the three AI build history links into the email in `docs/submission.md`, then paste the EMAIL LINES above into your email (subject exactly: `IIT Delhi – AI Engineer - 2027`).
3. In Render, make a new API key and delete the one that was pasted into a chat earlier; put the new one in `.env` as `RENDER_API_KEY`.
4. Optional: run the Lighthouse command in Known problems and add the scores to the README.
5. If the data looks old when you open it, run `cd backend && .venv/Scripts/python -m pipeline.run --research`, commit `frontend/public/data/`, then `npx vercel --prod` from `frontend/`.
