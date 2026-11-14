# Data sources

Status: **nothing verified yet.** Step 3 (the verification spike) probes each source from the laptop, from Render (Singapore) and from a GitHub Actions runner, and replaces "untested" below with what really happened. The planned sources come from CLAUDE.md section 5. Until then, treat every row as an assumption.

| Source | Laptop | Render | GitHub Actions | Notes / fallback |
|---|---|---|---|---|
| yfinance EOD price and volume (`SYMBOL.NS`) | untested | untested | untested | Fallback `.BO`. Quarterly financials are also used to cross-check results numbers. |
| NSE symbol to BSE scrip code | untested | untested | untested | Scrip master or ISIN route. Must work for any ticker. |
| BSE announcements API (`AnnSubCategoryGetData`) | untested | untested | untested | Needs a browser-like User-Agent and a bseindia.com Referer. Category and subcategory drive rule-based classification. |
| Results filing PDFs (via BSE announcements) | untested | untested | untested | Need text-extractable PDFs for Revenue, EBITDA, PBT, PAT. |
| Concall transcripts (via BSE announcements) | untested | untested | untested | Fallback: screener.in links. |
| NSE announcements API | untested | untested | untested | Fallback only. Blocks bots; no CAPTCHA bypass. |
| Gemini API | untested | untested | untested | Model names and free-tier limits to be recorded. |
| Groq API | untested | untested | untested | Fallback LLM provider. |
| Tavily search | untested | untested | untested | Management bios. 1,000 free credits a month. |
