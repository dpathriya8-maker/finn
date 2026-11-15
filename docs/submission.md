# Submission checklist and email

The project is built and pushed. What remains needs your accounts and your keys, so it is yours to do. Everything below is in the order that works.

## Before you send

Done (15 Nov 2026):

- [x] Keys in `.env` (Gemini; Groq and Tavily were not used), and the model names.
- [x] The Promise Tracker was run live, twice, and every decided verdict was read against its transcript (see the README table for what is right and what is known wrong).
- [x] "Ask the documents" was run live on all four companies.
- [x] Deployed: Render (free, Singapore) and Vercel, with CORS set to the Vercel URL. The Render check of the data sources is in [data-sources.md](data-sources.md): BSE answers 403 from Render, NSE, Yahoo and screener.in work.
- [x] The temporary debug route was removed once that check was done.

Still yours:

- [ ] Put the AI build history links into the email below (the planning chat, the Claude Code session, the chat where you studied the brief). They are the one thing I cannot know.
- [ ] Open the live app on a phone once: the Brief, an ITC card, Research with Info Edge, and ask one question. The first load after a sleep takes about a minute.
- [ ] In Render, create a new API key and delete the one that was pasted into a chat during the deploy.
- [ ] *Optional:* run `gh auth refresh -h github.com -s workflow` once and approve it in the browser. GitHub refuses a push that touches `.github/workflows/` without that scope, which is why the project has no CI workflow.

## The email

**To:** assessment@enam.com
**Subject:** IIT Delhi – AI Engineer - 2027

(The brief requires exactly this subject line, with en dashes as written.)

> Hello,
>
> Here is my submission for the AI Engineer Build Challenge.
>
> **FINN** is a mobile-first Financial Investment Agent for Indian stocks.
> - **Live app:** https://finn-mocha.vercel.app (open it on a phone; the research engine may take a minute to wake)
> - **Code:** https://github.com/dpathriya8-maker/finn
> - **Start with:** the [README](https://github.com/dpathriya8-maker/finn#readme) (what is verified and what is not, in a table) and [docs/write-up.md](https://github.com/dpathriya8-maker/finn/blob/main/docs/write-up.md) (the approach, the research behind the design, and what I left out).
>
> **What I built**
> - **Push:** a Morning Brief of 18 portfolio companies. One line counted in code ("1 risk to review", "Busy day: 6 of your companies filed", or "Quiet day"), then each company once with its filings under it in three lines, ranked so risks come first, with routine filings collapsed and a finite end. Results cards (Revenue, EBITDA, PBT, PAT, QoQ and YoY, read from the filing with no model and checked against Yahoo Finance); management-change cards with the filing's own profile; calm alerts on thresholds the user sets, each stating its reason and whether a same-day filing explains the move.
> - **Pull:** research on any NSE ticker from the company's own transcripts and annual report: "Delivered 2 of 5 promises that came due" counted in code, a Promise Tracker with the bad news first (Kept / Partly / Missed / Not followed up / Too early, each with its quote, document and page), what management said about the future, and "Ask the documents", which answers only from the filings or says "Not found in the documents".
> - **You:** a profile with no account: an optional name kept on the phone, the portfolio with mute, preferences, and how FINN works.
> - **In rupees:** optional amounts per company (kept on the phone only) show "Your ₹50,000 · ▼ ₹775 today" on the Brief, and a **What if** calculator in each open card and at the top of every Research page restates real moves in rupees (today, the last 30 days, and a slider from −20% to +20%). It predicts nothing and says it is not advice.
>
> **Key decisions and trade-offs**
> - A claim is shown only with its source, and a number is never a model's guess: a quote appears only if it is word for word on the page it cites; a verdict needs a quote from a later call; a promise is not called Kept, Partly or Missed before its date has passed; every count, change, margin and the "Delivered N of M" line is computed in code.
> - Rules before a model: most of the app uses no model (classification, the cards, retrieval, the summary lines). A model is used for three things only, a cheap one by default, every answer cached and every call logged: 222 successful calls, 81 from the cache, about 385,000 tokens in and 36,000 out, all on the free tier ($0).
> - The design follows research on investor attention and alert fatigue (short ranked Brief, risks first, a dot not a count, a reason on every alert, no confetti or streaks); the findings and how I used each, with their limits, are in the write-up. A headline takes two lines, not one, so a fact is never cut mid-way.
> - [24 decisions made up front and 115 while building](https://github.com/dpathriya8-maker/finn/blob/main/docs/decisions.md), [what was verified about each data source, including what failed](https://github.com/dpathriya8-maker/finn/blob/main/docs/data-sources.md), and the [build log](https://github.com/dpathriya8-maker/finn/blob/main/docs/build-log.md).
>
> **What I deliberately left out**
> - Push notifications and accounts (they need a server that knows who you are; FINN keeps settings on the phone).
> - News, broker notes and web search on the research side: research answers only from the company's own filings.
> - Company logos and people's photos (licensing, privacy and accuracy risk).
> - Following people and investing exist only as a labelled preview (the data is real; following triggers nothing and Invest is a "coming soon" sheet).
>
> **Where I'd take it next**
> - Rank the Brief by exposure to what each reader holds (the amounts are already kept on the phone).
> - Following people through exchange filings: insider trades, substantial acquisitions (SAST) and management changes.
> - A three-question first-time setup; one brief a day with quiet hours.
> - Hinglish across the app.
> - Investing through a SEBI-registered broker partner, as the revenue model.
>
> **AI build history** (required by the brief): `<share link of the planning chat on claude.ai>` · `<Claude Code session exports or links>` · `<share link of the chat where I studied the brief>`. The step prompts the planning chat wrote are also kept in [STEPS.md](https://github.com/dpathriya8-maker/finn/blob/main/STEPS.md), and every step's outcome is in the build log.
>
> **Known limits, stated plainly:**
> 1. The Promise Tracker's first run was too generous (24 of 54 verdicts Kept), so dates and numbers are now decided by code and a second reading was added. It is now 40 promises: 6 Kept, 1 Partly, 1 Missed, 3 Not followed up, 29 Too early. I read each decided verdict against its transcript and fixed what I found, but have not audited all of them.
> 2. The strong model's free quota (20 requests a day) ran out during re-runs, so most verdicts were made by the cheap model, `gemini-3.5-flash-lite`; each record says which model answered.
> 3. Naukri's 99acres billings promise was wrongly "Not followed up"; it is now Kept, with the Q2 FY27 call (page 5) as evidence, re-read on the live site.
> 4. A ticker I never prepared works live: TITAN was researched on the deployed engine in 34 seconds (four transcripts, 8 promises, a question answered with quotes, an unrelated one answered "Not found"). BSE answers HTTP 403 from Render, so the engine falls back to NSE, whose feed had no annual report for TITAN; the record says so.
> 5. HAL has only one call, so it has no tracker (the page says why); Asian Paints' annual report is over the 25 MB limit and is skipped.
> 6. The Interested tab, following people and Invest are a concept preview, marked Preview in the app. No push notifications.
> 7. Checked in a phone-sized browser at 360 and 390 px, light and dark, not on a real phone. Neither Vercel nor Render deploys on push; I deploy by hand.
>
> Thank you,
> DP

## If you are short of time

The app is deployed and the email above is ready. The only thing that cannot be done for you is the AI build history links.
