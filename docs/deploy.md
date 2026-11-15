# Deploying FINN

Backend on Render (free), frontend on Vercel (free). Neither needs a card. Do them in this order, because the frontend needs the backend's URL and the backend then needs the frontend's URL for CORS.

Keep the values from your local `.env` open, and do not paste any key into a chat.

## A. Backend on Render

1. Open https://dashboard.render.com and sign in with GitHub.
2. Click **New +** then **Blueprint**.
3. If Render asks to connect GitHub, choose **Only select repositories**, pick `dpathriya8-maker/finn`, and save.
4. Select the `finn` repository, branch `main`. Render reads `render.yaml` and shows one service: **finn-api**, Web Service, Free, Singapore.
5. Render now asks for the environment variables marked "sync: false". Fill them in:

   | Variable | What to enter |
   |---|---|
   | `ALLOWED_ORIGINS` | For now `http://localhost:3000`. You change it in step C. |
   | `ADMIN_TOKEN` | A long random string. Make one with `py -c "import secrets; print(secrets.token_urlsafe(32))"` and keep it somewhere private. |
   | `GEMINI_API_KEY`, `GROQ_API_KEY`, `TAVILY_API_KEY` | From your `.env`. |
   | `LLM_CHEAP_MODEL`, `LLM_STRONG_MODEL`, `LLM_FALLBACK_MODEL` | From your `.env` (Step 3 records the model names that work). |
   | `DAILY_FRESH_RESEARCH_CAP` | `20` is a sensible start. |

   Variables you do not have yet can stay empty if Render allows it. If it insists on a value, type `x` and fix it later in the service's **Environment** tab.
6. Click **Deploy Blueprint**. The first build takes about 3 to 5 minutes.
7. When the service shows **Live**, open `https://<your-service>.onrender.com/health` in a browser. You should see `{"status":"ok","version":"0.1.0","time_ist":"..."}`.
8. Copy the service URL (`https://<your-service>.onrender.com`, no trailing slash). Send it to the coding agent if you want help with the next steps.

If the build fails, open the service's **Logs** tab. The two things worth checking against Render's docs on the first deploy are that `$PORT` is accepted in the start command and that `PYTHON_VERSION` takes the full version `3.14.10`.

## B. Frontend on Vercel

1. Open https://vercel.com/new and sign in with GitHub.
2. Import `dpathriya8-maker/finn`. If it is not listed, click **Adjust GitHub App Permissions** and allow that repository.
3. On the configure screen:
   - **Framework Preset**: Next.js (detected automatically).
   - **Root Directory**: click **Edit** and choose `frontend`. This is the one setting that must be changed.
   - Leave the build and output settings at their defaults.
4. Open **Environment Variables** and add:
   - Name `NEXT_PUBLIC_API_URL`, value the Render URL from step A8. No trailing slash.

   Set it before the first deploy: the value is built into the page, so changing it later needs a redeploy.
5. Click **Deploy**. It takes about a minute.
6. Copy the production URL Vercel shows (`https://<project>.vercel.app`).

## C. Let the frontend talk to the backend (CORS)

1. In Render, open **finn-api** then **Environment**.
2. Edit `ALLOWED_ORIGINS` to the Vercel production URL, for example `https://finn-xxxx.vercel.app`. It must match exactly: `https` and no path or trailing slash. For more than one origin, separate them with commas. `http://localhost:3000` is always allowed.
3. Save. Render redeploys by itself (about a minute).
4. Open the Vercel URL on your phone. After a short "Engine waking up..." the pill should turn green: **Engine online**. Below the title you should see "Data as of ..." with the time the data was produced.

## D. Add to home screen

- iPhone (Safari): Share, then **Add to Home Screen**.
- Android (Chrome): the three-dot menu, then **Install app** or **Add to Home screen**.

## E. Check which data sources work from Render (Step 3)

Done on 15 Nov 2026, and the temporary `/debug/sources` route has been removed. Result: Yahoo, NSE announcements and screener.in work from Render; **BSE answers HTTP 403** on every endpoint. The table is in [data-sources.md](data-sources.md). Because of that, an unprepared ticker fails on Render at "finding the company" with a stated reason, while the four prepared companies do not depend on it.

## F. Turn on the Promise Tracker (needs your API keys)

Until a model is configured, Research shows what management said about the future (found by rule) and "No verdict yet". To get verdicts and written answers:

1. In your local `.env` set `GEMINI_API_KEY` and `LLM_CHEAP_MODEL` (and, if you want, `LLM_STRONG_MODEL`, `GROQ_API_KEY` and `LLM_FALLBACK_MODEL`; a model written `groq:name` goes to Groq). Never paste a key into a chat.
2. From `backend/`: `.venv/Scripts/python -m pipeline.research`. This reads the four research companies again (from the saved documents, so no downloads: add `--offline`), builds the Promise Tracker, and writes `frontend/public/data/research/*.json`. It keeps an existing record that already has verdicts if a later run has no key.
3. **Read the first verdicts against the transcripts yourself** (every card shows its quote and page, and "Open at that page"). This is the first real run of the model path, so expect to tune the two prompts in `backend/app/pull/promises.py`.
4. `python -m app.core.llm` prints how many calls were made and their tokens, for the cost table in `docs/cost.md`.
5. Commit and push the changed JSON. Put the same keys in Render's environment so unprepared tickers get verdicts too.

## G. Smoke test after deploying

On your phone, in this order: the Brief loads with "Data as of"; open the ITC card and the Apollo Hospitals card (results and management cards); Alerts shows a count; Research lists four companies and opens Info Edge with quotes; ask "What did management say about capex?" (the first ask after a sleep says the engine is waking, then answers); then try a company that is not listed, such as TITAN. It should show "Reading TITAN's filings" with its stages, then a record, or a stated reason if the exchanges refuse Render's address. If that fails, the four prepared companies are unaffected.

## If something looks wrong

| You see | Why and what to do |
|---|---|
| "Engine not configured" | `NEXT_PUBLIC_API_URL` was missing at build time. Add it in Vercel (Settings, Environment Variables), then Deployments, the three dots, **Redeploy**. |
| "Engine waking up..." for up to a minute | Normal on the free tier: Render sleeps after 15 idle minutes and takes about a minute to wake. The pill retries every 5 seconds for 90 seconds. |
| "Engine offline" after 90 seconds | Open Render's **Logs**. If the service is Live, check CORS: in the phone browser's console (or desktop dev tools) a CORS error means `ALLOWED_ORIGINS` does not exactly match the Vercel URL. |
| Page loads but "Data unavailable right now" | `frontend/public/data/meta.json` is missing from the deploy. Check the file is in the repo and Vercel's root directory is `frontend`. |
| HTTP 429 | The per-IP limit (30 requests a minute) was hit. Wait a minute. |

## Known limits

- **Memory.** Measured locally: the API idles at 63 MB, and a cold research of a company never fetched before (four transcripts and an 11.5 MB annual report) peaked at 131 MB, so the 512 MB free instance has plenty of room.
- The per-IP rate limit reads the client IP from `X-Forwarded-For`, which a determined client could spoof behind Render's proxy. The real guard on the free LLM quota is the global `DAILY_FRESH_RESEARCH_CAP`, not the per-IP limit.
- The GitHub Actions workflows (CI and the scheduled data refresh) need the `workflow` scope on your GitHub login: run `gh auth refresh -h github.com -s workflow` once and approve it in the browser.
