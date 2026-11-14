# Architecture

Draft taken from CLAUDE.md section 3. The final diagram and write-up come in Step 11.

```
[pipeline (Python)]  --runs daily / on demand-->  frontend/public/data/*.json  --static-->  [Next.js on Vercel]
   prices (yfinance) · announcements (BSE JSON API) · docs (BSE filings PDFs, screener fallback)
   classify (rules first, cheap LLM only if needed) · results extraction · bios · priority scores
[FastAPI on Render]  <-- only for PULL on a ticker not precomputed, and Ask-the-docs
```

- **PUSH is precomputed.** The pipeline writes raw metrics (volume ratio, % move) and classified, ranked filings to static JSON. The browser applies the user's thresholds, so changing a setting is instant.
- **PULL** for the demo research companies is precomputed too. Any other NSE ticker calls the FastAPI backend, which may be asleep on Render's free tier, so the UI shows a "waking up research engine" state.
- **Settings** live in the browser (localStorage). No accounts.
- **Keys** exist only in the pipeline and backend environments, never in the frontend.

Why each choice was made: [decisions.md](decisions.md). What has actually been verified about each data source: [data-sources.md](data-sources.md).
