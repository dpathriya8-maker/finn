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
> - **Start with:** the [README](https://github.com/dpathriya8-maker/finn#readme) (what is verified and what is not, in a table) and [docs/write-up.md](https://github.com/dpathriya8-maker/finn/blob/main/docs/write-up.md) (the approach in two pages).
>
> **Push:** a Morning Brief of 18 portfolio companies, ranked so risks come first; results cards (Revenue, EBITDA, PBT, PAT, QoQ and YoY, read from the filing with no model and checked against Yahoo Finance); management-change cards with the filing's own profile; alerts on thresholds the user sets, instant to change.
> **Pull:** research on any NSE ticker from the company's own transcripts and annual report: what management said about the future, a Promise Tracker (Kept / Partly / Missed / Not followed up / Too early, each with its quote, document and page), and "Ask the documents", which answers only from the filings or says "Not found in the documents".
>
> **How it avoids making things up:** a quote is shown only if it is word for word on the page it cites; a verdict needs a quote from a later call; when a promise is due, every number, change and margin is computed in code, and a promise is not called Kept, Partly or Missed before its date has passed. A source that disagrees is shown, not hidden.
>
> **Cost and efficiency:** most of the app uses no model (classification, the cards, retrieval). A model is used for three things only, with a cheap model by default, every answer cached by its input and prompt version, and every call logged. Measured over the whole build session (two live runs of the tracker and their re-runs): 210 successful calls, 75 of them answered from the cache, about 367,000 tokens in and 35,000 out, all on the free tier ($0).
>
> **Decisions and history:** [24 decisions made up front and 84 while building](https://github.com/dpathriya8-maker/finn/blob/main/docs/decisions.md), [what was verified about each data source, including what failed](https://github.com/dpathriya8-maker/finn/blob/main/docs/data-sources.md), and the [build log](https://github.com/dpathriya8-maker/finn/blob/main/docs/build-log.md).
>
> **AI build history** (required by the brief): `<share link of the planning chat on claude.ai>` · `<Claude Code session exports or links>` · `<share link of the chat where I studied the brief>`. The step prompts the planning chat wrote are also kept in [STEPS.md](https://github.com/dpathriya8-maker/finn/blob/main/STEPS.md), and every step's outcome is in the build log.
>
> **Known limits, stated plainly:** (1) The first run of the Promise Tracker was too generous (24 of 54 verdicts Kept), so I made dates and numbers decided by code and added a second reading; it is now 5 Kept, 1 Partly, 1 Missed, 4 Not followed up and 29 Too early over 40 promises. I read each decided verdict against the transcript but have not audited all of them, and one is known wrong: Naukri's "billings growth to recover in Q1" (about 99acres) shows Not followed up although the Q1 call discusses it, because my search did not surface that passage. (2) The strong model's free quota (20 requests a day) ran out during re-runs, so these verdicts were made by the cheap model, `gemini-3.5-flash-lite`; each record says which model answered. (3) BSE answers HTTP 403 from Render, so research on a ticker that was not prepared in advance (I tried TITAN) fails there with a stated reason; the four prepared companies (Bajaj Finance, Asian Paints, HAL, Info Edge) and everything in the Brief and Alerts are unaffected. (4) HAL has only one call in the window, so it has no tracker. (5) No push notifications.
>
> Thank you,
> DP

## If you are short of time

The app is deployed and the email above is ready. The only thing that cannot be done for you is the AI build history links.
