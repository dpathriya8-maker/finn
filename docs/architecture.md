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
- **Where the pipeline runs (decided in Step 3):** on the developer's laptop for now, committing its JSON, because BSE and NSE are only proven reachable from a home connection. Render and GitHub Actions take over once the probe table says they can reach the sources.
- **Cards that read a filing (Step 8):** for each results or management filing in the window the pipeline downloads the PDF once (allow-listed hosts, 25 MB cap), reads it without a model, keeps what it read in a SQLite cache, and builds the card on every run. A results card is checked against Yahoo's quarterly figures; a management card shows only what the filing itself says. Details: [decisions.md](decisions.md) S50 to S66.
- **Sources:** BSE first (category and subcategory feed the rules), NSE for issuers BSE does not list (CDSL), Yahoo for prices and cross-checks, exchange PDFs for results, transcripts and annual reports.
- **How PULL works (Steps 9 and 10):** for a company, find the last four concall transcripts and the latest annual report on the exchange, download and read them once, cut them into chunks that keep their page, and find what management said about the future by rule. If a model is configured, it extracts promises and judges them against later calls; every quote must be word for word on its page and every verdict needs a later quote, or it is set back to "Too early". "Ask the documents" ranks chunks by BM25, refuses before any model is asked if the documents lack the question's words, and shows only quotes that are in them. The four demo companies are prepared in advance (records with the front end, their documents with the backend); any other ticker is a background job the screen follows.
- **Settings** live in the browser (localStorage). No accounts.
- **Keys** exist only in the pipeline and backend environments, never in the frontend.

Why each choice was made: [decisions.md](decisions.md). What has actually been verified about each data source: [data-sources.md](data-sources.md).
