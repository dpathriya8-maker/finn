# Submission checklist and email

The project is built and pushed. What remains needs your accounts and your keys, so it is yours to do. Everything below is in the order that works.

## Before you send (about 45 minutes)

- [ ] **Keys.** Create `finn/.env` from `.env.example` and fill in at least `GEMINI_API_KEY` and `LLM_CHEAP_MODEL` ([Google AI Studio](https://aistudio.google.com) shows which Flash and Flash-Lite names are free). Optional: `GROQ_API_KEY` and `LLM_FALLBACK_MODEL` as a backup. Do not paste any key into a chat; your chats go to ENAM as build history.
- [ ] **Run the Promise Tracker once.** From `backend/`: `.venv/Scripts/python -m pipeline.research`. Open the four companies in the app (`npm run dev`) and **read the verdicts against the transcripts**. Every card has its quote and "Open at that page". If a verdict looks wrong, the two prompts are in `backend/app/pull/promises.py`. Then `python -m app.core.llm` gives the call and token table for the README's cost section.
- [ ] **Commit and push** the changed `frontend/public/data/research/*.json`.
- [ ] **Refresh the portfolio data on the day you send.** From `backend/`: `.venv/Scripts/python -m pipeline.run` (about 30 seconds), then commit and push `frontend/public/data/`. The Brief counts its windows from the data's own timestamp, so old data still shows something and says how old it is, but fresh filings are better.
- [ ] **Deploy** following [deploy.md](deploy.md): A (Render), B (Vercel), C (CORS), then **E** (it tells you whether BSE and NSE accept Render's address, which decides whether an unprepared ticker works on the live site), then F and G.
- [ ] **Update the README** "What is verified" table with what you saw: the live URL, and whether the model path and the Render check worked.
- [ ] **Remove the temporary debug route** once section E is done: delete `backend/app/api/debug.py`, `backend/probes/`, `backend/tests/test_debug_route.py` and their lines in `backend/app/main.py`. It is admin-token protected and closed without a token, so it is safe to leave if you are short of time.
- [ ] Run `git status` (nothing should be untracked that matters) and push.
- [ ] *Optional:* run `gh auth refresh -h github.com -s workflow` once and approve it in the browser. GitHub refuses a push that touches `.github/workflows/` without that scope, which is why the project has no CI workflow yet; once it is granted, the coding agent can add one.

## The email

**To:** assessment@enam.com
**Subject:** IIT Delhi – AI Engineer - 2027

(The brief requires exactly this subject line, with en dashes as written.)

> Hello,
>
> Here is my submission for the AI Engineer Build Challenge.
>
> **FINN** is a mobile-first Financial Investment Agent for Indian stocks.
> - **Live app:** `<your Vercel URL>` (open it on a phone; the research engine may take a minute to wake)
> - **Code:** https://github.com/dpathriya8-maker/finn
> - **Start with:** the [README](https://github.com/dpathriya8-maker/finn#readme) (what is verified and what is not, in a table) and [docs/write-up.md](https://github.com/dpathriya8-maker/finn/blob/main/docs/write-up.md) (the approach in two pages).
>
> **Push:** a Morning Brief of 18 portfolio companies, ranked so risks come first; results cards (Revenue, EBITDA, PBT, PAT, QoQ and YoY, read from the filing with no model and checked against Yahoo Finance); management-change cards with the filing's own profile; alerts on thresholds the user sets, instant to change.
> **Pull:** research on any NSE ticker from the company's own transcripts and annual report: what management said about the future, a Promise Tracker (Kept / Partly / Missed / Too early, each with its quote, document and page), and "Ask the documents", which answers only from the filings or says "Not found in the documents".
>
> **How it avoids making things up:** a quote is shown only if it is word for word on the page it cites; a verdict needs a quote from a later call; every number, change and margin is computed in code. A source that disagrees is shown, not hidden.
>
> **Cost and efficiency:** most of the app uses no model (classification, the cards, retrieval). A model is used for three things only, with a cheap model by default, every answer cached by its input and prompt version, and every call logged. Measured on the first live run: the Promise Tracker for 3 companies took 25 model calls and about 71,000 tokens in, 11,000 out, on the free tier ($0); a second run was answered from the cache.
>
> **Decisions and history:** [24 decisions made up front and 84 while building](https://github.com/dpathriya8-maker/finn/blob/main/docs/decisions.md), [what was verified about each data source, including what failed](https://github.com/dpathriya8-maker/finn/blob/main/docs/data-sources.md), and the [build log](https://github.com/dpathriya8-maker/finn/blob/main/docs/build-log.md).
>
> **AI build history** (required by the brief): `<share link of the planning chat on claude.ai>` · `<Claude Code session exports or links>` · `<share link of the chat where I studied the brief>`. The step prompts the planning chat wrote are also kept in [STEPS.md](https://github.com/dpathriya8-maker/finn/blob/main/STEPS.md), and every step's outcome is in the build log.
>
> **Known limits, stated plainly:** `<edit after your check: the model path ran live on 4 companies (3 with verdicts, 54 in total; HAL has only one call in the window); no verdict is marked Missed in this data, so the tracker may be generous; "Ask the documents" has not yet been run against a live model; BSE/NSE reachability from Render is `<edit after deploy.md section E>`; no push notifications>`.
>
> Thank you,
> DP

## If you are short of time

The minimum that still makes a credible submission: deploy (A, B, C), push, and send the email with the limits paragraph saying the Promise Tracker's verdicts have not been run against a live model (the README already says so). The app is honest in that state: Research shows what management said, with sources, and "No verdict yet".
