# Data sources

Verified on **15 Nov 2026** from the developer's Windows laptop (Step 3). Two columns are still open: **Render** waits for the deploy (the probe route is already built, see "Re-running the probes"), and **GitHub Actions** needs the `workflow` scope on the GitHub login before a probe workflow can be pushed. Gemini, Groq and Tavily were not tested because no API keys exist yet. "Works" below means tested for real; "untested" means exactly that.

## Summary

| Source | Laptop | Render | GitHub Actions | Notes / fallback |
|---|---|---|---|---|
| yfinance prices (`SYMBOL.NS`) | Works: 63 daily bars in 0.2 to 1.7 s, 4 of 4 tickers | untested | untested | `.BO` fallback works but is thin for some tickers (RELIANCE.BO and BAJFINANCE.BO returned 1 bar in 2 months), so `.NS` is the source and `.BO` the fallback. Use raw, not split-adjusted, prices. |
| yfinance quarterly income statement | Works: 5 to 6 quarters, 4 of 4 tickers | untested | untested | Cross-check only. Yahoo skips quarters (RELIANCE and KAYNES have no Sep-2025), has no EBITDA for lenders (BAJFINANCE), and lags a fresh filing (KAYNES Sep-2026 is absent). |
| NSE symbol to BSE scrip code (BSE scrip master + NSE `EQUITY_L.csv`, joined on ISIN) | Works: 2,294 of 2,391 NSE equity symbols (95.9%); 21 of our 22 tickers | untested | untested | **CDSL has no BSE scrip** in BSE's master: it is an NSE-only feed. Never match on name (BSE's quote search for "CDSL" returns ICDS Ltd). |
| BSE announcements API | Works: 0.1 to 0.5 s a request, 50 rows a page | untested | untested | Needs User-Agent, Referer, Origin and Accept together (User-Agent plus Referer alone is refused with 403). At most 365 days per request. |
| BSE results PDFs | Works: 3 of 3 downloaded (1.2, 8.6, 18.8 MB, each under 1.5 s); all text-extractable | untested | untested | Tables are findable by page. Units and layout differ per company (see "Results filings"). |
| BSE concall transcripts | Works: the last 4 quarterly transcripts were found for 3 of 3 companies, looking back up to 13 months | untested | untested | Filed under `Earnings Call Transcript` **or** `Analyst / Investor Meet`; the text must be checked too. Clean extractable text. |
| BSE annual reports | Found for 3 of 3 (8 to 22 MB) | untested | untested | `Others / Reg. 34 (1) Annual Report`. Bajaj's 22 MB is close to the 25 MB cap. |
| NSE announcements API | Works with a normal browser-style session (cookies from the home page first), with a date range | untested | untested | The only feed for CDSL. Keyed by symbol, so no scrip-code mapping. Akamai-protected, so cloud IPs may be refused. Attachments are served from `nseindia.in` as well as `nseindia.com`. |
| screener.in company page | Works: 4 of 4, with 18 to 39 transcript links each | untested | untested | Fallback for transcript links. CDSL's links point to NSE's archive. |
| Gemini API | untested: no key | untested | untested | See "LLM providers and Tavily". |
| Groq API | untested: no key | untested | untested | Fallback LLM. |
| Tavily search | untested: no key | untested | untested | Management bios. |

## 1. yfinance (prices and quarterly figures)

- `Ticker("RELIANCE.NS").history(period="3mo", interval="1d", auto_adjust=False)` returned 63 bars; the last bar was Friday 13 Nov 2026 for all four tickers. Columns: Open, High, Low, Close, Adj Close, Volume.
- `quarterly_income_stmt` gives `Total Revenue`, `EBITDA`, `Pretax Income` and `Net Income` in rupees, five columns for RELIANCE, KAYNES and BAJFINANCE and six for CDSL. Divide by 10^7 for crore.
- Cross-checks against the filings (Reliance and Bajaj Finance consolidated): Pretax Income equals the filing's profit before tax exactly (Reliance 38,613 Cr; Bajaj 8,537 Cr). Yahoo's revenue is net of excise duty (Reliance filing 332,861 minus excise 2,260 equals Yahoo's 330,601). Yahoo's net income is the profit **attributable to owners** (Reliance 25,548 versus 29,250 total profit after tax). Kaynes' preceding-quarter figures in the new filing are marked "Restated", so Yahoo's original PBT differs. So the cross-check badge has to say "differs from Yahoo", not "wrong".

## 2. NSE symbol to BSE scrip code

- BSE: `ListOfScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active` returns 5,147 active equities (1.8 MB, 0.7 s) with `SCRIP_CD`, `Scrip_Name`, `ISIN_NUMBER`, `scrip_id`, `GROUP`.
- NSE: `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` lists 2,635 rows (2,391 series EQ, 210 BE, 34 BZ) with `SYMBOL`, `NAME OF COMPANY` and `ISIN NUMBER`. The header names carry stray spaces.
- Joining on ISIN maps 95.9% of NSE EQ symbols. No ISIN had more than one BSE row. Punctuation symbols work (`M&M`, `BAJAJ-AUTO`).
- **CDSL does not map.** Its ISIN (INE736A01011) is absent from BSE's master even with every status and segment. BSE's own quote search for "CDSL" returns "ICDS Ltd" (511194), so a name match would silently attach the wrong company. The resolver returns `bse_code = None` and the pipeline must use the NSE feed. Code 540710, which I first guessed, is Capacite Infraprojects.
- The `bse` PyPI package was not needed.
- Both lists change slowly; they are cached for 24 hours, and a stale copy is used if a download fails.

## 3. BSE announcements API

`GET https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w` with `pageno`, `strCat=-1`, `strPrevDate=YYYYMMDD`, `strScrip=<scrip code or empty for all>`, `strSearch=P`, `strToDate=YYYYMMDD`, `strType=C`, `subcategory=-1`.

- **Headers:** `User-Agent` (a browser string), `Referer: https://www.bseindia.com/`, `Origin: https://www.bseindia.com` and `Accept: application/json, text/plain, */*`. With User-Agent and Referer only, or with no headers, BSE returns `403 Access Denied` (an HTML page). No cookies, no key.
- **Response:** `{"Table": [rows], "Table1": [{"ROWCNT": total}]}`. Row fields: `NEWSID` (GUID), `SCRIP_CD`, `SLONGNAME` (company), `NEWSSUB` (subject), `HEADLINE` and `MORE` (body text), `CATEGORYNAME`, `SUBCATNAME`, `NEWS_DT` and `DT_TM` (IST, no zone), `ATTACHMENTNAME` (a PDF file name), `Fld_Attachsize` (bytes), `QUARTER_ID`, `CRITICALNEWS`, `NSURL`.
- **Attachment URL:** `https://www.bseindia.com/xml-data/corpfiling/AttachLive/<ATTACHMENTNAME>`; older filings move to `.../AttachHis/`. Downloads need the same headers (with `Accept: application/pdf,*/*`) and returned in 0.2 to 1.4 s.
- **Pagination:** 50 rows a page; `ROWCNT` is the total. A full day for all companies (12 Nov 2026) was 1,920 rows in 39 pages, 20 s in total, no duplicates. Count unique `NEWSID`s, because a new filing landing mid-read can shift a row onto two pages.
- **Date span:** at most 365 days. 366 days returns HTTP 400. Longer histories are fetched in 365-day windows.
- **Rate behaviour:** about 70 requests in one session, 0.1 to 0.5 s each, no throttling and no 429. I deliberately did **not** stress-test it: it is someone else's production API, and a load test was not needed. The client sends one request at a time with a 0.25 s pause.
- **Quirks:** `NEWSSUB` sometimes starts with `"<Company> - <scrip code> - "` (strip it); one category is `' Corp Action'` with a leading space; `SUBCATNAME` can be null (`Others`); the filing date can lag the real event by a day.
- **Volume:** 8 companies over 90 days gave 267 rows; a typical large cap gives 40 to 50 rows in 90 days.

### Vocabulary seen (one full trading day plus 8 companies over 90 days)

8 categories and 64 category/subcategory pairs. This is the draft mapping to our 17 categories for Step 5. "Routine" marks pairs that should be collapsed whatever the category.

| Our category | BSE category / subcategory pairs |
|---|---|
| results | `Result / Financial Results`; `Board Meeting / Outcome of Board Meeting` when the text says financial results |
| management_change | `Company Update /` Change in Management, Change in Directorate, Resignation of Director, Resignation of Chief Financial Officer (CFO), Resignation of Chief Executive Officer (CEO), Resignation of Chairman and Managing Director, Resignation of Statutory Auditors, Appointment of Statutory Auditor/s, Appointment of Company Secretary / Compliance Officer, Resignation of Company Secretary / Compliance Officer, Cessation, Retirement |
| m_and_a | `Company Update /` Acquisition, Scheme of Arrangement, Diversification / Disinvestment, Joint Venture, Restructuring, Open Offer, Public Announcement |
| fund_raise | `Company Update /` Raising of Funds, Issue of Securities, Qualified Institutional Placement, Preferential Issue, Allotment of Equity Shares; `Corp. Action / Bonds / Right issue`. Routine: Allotment of ESOP / ESPS, Monitoring Agency Report, Reg. 32 (1), (3) Statement of Deviation & Variation |
| litigation | `Company Update / Intimation of meeting of Committee of Creditors`; text rules for court, tribunal, penalty, SEBI order and tax demand inside `General`. Only 4 of 1,920 rows in the sampled day |
| credit_rating | `Company Update / Credit Rating`; `Others / Reg. 54 - Asset Cover details` (routine) |
| dividend | `Corp. Action / Dividend`, `Record Date`; ` Corp Action / Dividend Updates`; buy-backs (`Buy back`, `Post Buyback Public Announcement`, ` Corp Action / Daily Buy Back of equity shares`), a judgement call |
| bonus_split | `Corp. Action / Bonus`, `Sub-division / Stock Split` |
| capex | text rules inside `General` and `Press Release` (new plant, capacity, expansion) |
| press_release | `Company Update /` Press Release / Media Release (and "(Revised)"), Award of Order / Receipt of Order. Routine: Newspaper Publication |
| earnings_call | `Company Update / Earnings Call Transcript`; any row whose text says transcript |
| investor_meetings | `Company Update /` Analyst / Investor Meet, Investor Presentation (routine) |
| insider_trading | `Insider Trading / SAST /` Closure of Trading Window, Disclosures under Reg. 29(2) of SEBI (SAST) Regulations; `Company Update / Code of Conduct under SEBI (PIT) Regulations` (routine) |
| agm_egm | `AGM/EGM / AGM`, `EGM`; `Board Meeting / Board Meeting` (the intimation); `Company Update /` Board Meeting Rescheduled, Meeting Updates, Revision of outcome; `Others / Reg. 34 (1) Annual Report` (routine) |
| postal_ballot | `AGM/EGM / Postal Ballot` |
| pledging | no pair exists; encumbrance and pledge disclosures are text matches (0 hits in the sampled day) |
| unclassified | `Company Update /` General (28% of rows, needs the subject text), Clarification, Strikes / Lockouts / Disturbances, Amendments to Memorandum & Articles, Change in Registered Office Address, Certificate under Reg. 74 (5) (routine); `Others` with no subcategory (REIT and InvIT disclosures) and `Outcome without intimation` |

NSE's `desc` field is one flat label. The 18 values seen for CDSL and RELIANCE over 90 days map the same way: Analysts/Institutional Investor Meet/Con. Call Updates, Updates, General Updates, Credit Rating, Outcome of Board Meeting, Press Release, Copy of Newspaper Publication, Trading Window, Change in Management, Other Restructuring, Allotment of Securities, News Verification, Retirement, Appointment, Investor Presentation, Action(s) taken or orders passed, Amendment to AOA/MOA, Shareholders meeting.

## 4. Results filings

Latest quarterly results PDF for each test company, found as `Result / Financial Results`. The same file is usually also attached to the `Outcome of Board Meeting` row.

| Company | Filed | PDF | Text? | Where the table sits | Unit |
|---|---|---|---|---|---|
| RELIANCE | 30 Oct 2026 | 31 pages, 8.6 MB | yes | consolidated statement on page 10 (standalone later) | Rs crore |
| KAYNES | 14 Nov 2026 | 25 pages, 1.2 MB | yes | standalone page 7, consolidated page 8 | Rs million |
| BAJFINANCE | 19 Oct 2026 | 48 pages, 18.8 MB | yes | **standalone** page 4 first, consolidated page 14 | Rs crore |

Feasible, but not trivially: Revenue from operations, Total income, finance costs, depreciation, profit before tax and profit after tax are present for the current quarter, the preceding quarter and the same quarter last year (SEBI's column order: current quarter, preceding quarter, corresponding quarter last year, then half-year or nine-month figures, then the year). EBITDA is not reported; it has to be built from profit before tax plus finance costs plus depreciation (less other income), and the definition should be shown. Hazards the extractor must handle:

- Units differ (crore, million, lakh) and the unit line sits in the table header.
- Consolidated and standalone both appear; consolidated should win, and the card should say which it used.
- A serial-number column leaks into some rows (`'3', '1,270.17', ...`).
- Some thousands separators are extracted as dots (`17.369.35`), the rupee sign as `t` or `~`, and one value arrived garbled (`4,2so.n`). A number that cannot be read must be dropped, not guessed.
- Reliance's table spans word groups that a simple row grouping splits; Kaynes' preceding quarter is "Restated".
- Plain-text order is not column order, so pages must be read with word positions.

**Step 3's plan was a model reading the page text. Step 8 replaced it with no model at all** (decision S50): the figures are read from word positions with PyMuPDF, every kept number is a token printed in the filing, and QoQ, YoY, margins and EBITDA are computed in code and cross-checked against Yahoo. Seven very different real filings were the test set:

| Company | What the filing is | What the extractor does |
|---|---|---|
| RELIANCE | clean text, consolidated page 10, Rs crore; a header typo ("Seo'25" for Sep'25) | month read by fuzzy match; full card; revenue, PBT, PAT match Yahoo |
| KAYNES | **Rs million** | converted to crore; Yahoo has not published the quarter, so "not cross-checked" |
| BAJFINANCE | a lender: revenue is interest income, no meaningful EBITDA | EBITDA and the revenue check are skipped; PBT matches Yahoo |
| TATASTEEL | statements **rotated 270 degrees** in the PDF; Indian lakh grouping (`1,41,887.37`) | words are mapped through the page's rotation matrix; full card |
| ITC | prints the **year-ago column second** (June 2026 third); revenue includes excise duty that Yahoo excludes; its profit row is damaged in the PDF's own text (`4229.33 51B6.55` stuck in the label) | column order read from the header dates; excise taken into account in the check; the damaged figures are recomputed as PBT less tax and labelled as computed |
| BHARTIARTL | a **scan** (OCR text: digits swapped for letters, figures stuck in labels) | shows only the periods whose profit before tax Yahoo confirms; PBT only, with a stated reason |
| APOLLOHOSP | a scan, **nothing Yahoo can confirm** | refuses: "Figures not shown", with the reason and a link to the filing |

Findings worth remembering:

- A results PDF is often one attachment shared by several announcements (a board-outcome letter holds the results *and* a director's retirement), so one file is downloaded once per company per run.
- Attachments are 1 to 19 MB; the 25 MB cap was never hit by a results filing.
- BSE moves attachments from `AttachLive` to `AttachHis` as they age; the downloader tries both.
- Yahoo's quarterly figures lag a fresh filing by days (KAYNES, filed 14 Nov, was not there on 15 Nov), and its net income is the owners' share, not total profit.
- Page text order is not column order, a misread digit still parses as a number, and an unreadable figure is dropped, never guessed.

### Management-change filings

Four real ones (HDFC Bank twice, Tata Steel, Apollo Hospitals) show the range: a one-page letter; a four-page letter with Schedule III annexures; one paragraph inside a 24-page board-outcome letter whose other 22 pages are the results statements; and a 32-page scan whose reading order is scrambled. SEBI's disclosure format asks for the reason, the date, the term and, **for an appointment, a brief profile of the person**, so the filing itself is a primary-source bio and no web search is needed to say who is joining. The card therefore shows only literal spans: the person and role (from the announcement's headline, completed by the filing's own sentence when the headline is cut short), the date after "effective" or "w.e.f.", the term, the DIN, and the filing's "Profile" section with its page. It names nothing it cannot find.

## 5. Concall transcripts and annual reports

- 18 months of announcements per company, in 365-day windows. RELIANCE: 5 filed as `Earnings Call Transcript` plus the July 2026 one filed as `Analyst / Investor Meet`. KAYNES: 6 plus 1. BAJFINANCE: all 7 under `Analyst / Investor Meet`, with the word "transcript" only in the body. The probe's 365-day window found 4 transcript-like filings for each of the three, but KAYNES' fourth is a Dec 2025 investor-meet filing; its fourth earnings-call transcript (Nov 2025) falls just outside that window. So the last 4 quarters of transcripts exist for all three, and the pipeline should look back about 14 months, not 12.
- Transcripts follow results by 2 to 5 days. A fresh result (KAYNES, 14 Nov) has no transcript yet.
- Text is clean: 20 to 29 pages, 52k to 96k characters, no empty pages, speaker lines and a Moderator in two of three. Page 1 is the exchange cover letter. Non-ASCII is limited to dashes, curly quotes and bullets, plus the occasional `ﬁ` ligature, so quote matching must normalise Unicode (NFKC) and whitespace. A normalised quote spanning a line break matched the normalised text.
- Annual reports: `Others / Reg. 34 (1) Annual Report`, one a year. RELIANCE 10.5 MB, KAYNES 14.7 MB, BAJFINANCE 22.0 MB. Large groups can exceed the 25 MB cap, so annual reports need a separate, larger cap, streaming to disk, and a section filter before any text reaches a model.
- screener.in: `https://www.screener.in/company/<SYMBOL>/consolidated/` loads without login (190 to 250 KB) and lists transcript links (RELIANCE 20, KAYNES 18, BAJFINANCE 39, CDSL 29). Use it only when the exchange filing cannot be found.

## 6. NSE announcements API

- Needs a session: `GET https://www.nseindia.com/` first (sets Akamai cookies), then `GET https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=<SYMBOL>&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY` with a browser User-Agent, `Accept: application/json` and a `Referer` of the corporate-filings page. No CAPTCHA appeared, and none was attempted to be bypassed.
- Without dates it returns the whole history (CDSL 827 rows, 0.6 MB; RELIANCE 3,377 rows, 3 MB). With a 90-day range: CDSL 27 rows in 0.2 s, RELIANCE 46 rows in 0.1 s, the same count BSE gave for the same window.
- Fields: `symbol`, `sm_name`, `sm_isin`, `desc`, `an_dt` (`15-Nov-2026 18:08:06`), `attchmntText` (a one-line description), `attchmntFile`, `fileSize` (`306.78 KB`), `seq_id`, `smIndustry`.
- Attachments come from `nsearchives.nseindia.in` (and `.com`), so the SSRF allow-list covers both.

## 7. LLM providers and Tavily (not tested)

No `.env` exists, so no key was available. What the providers document, from web searches on 15 Nov 2026 (**unverified with a key**):

- **Gemini:** limits are per project, in requests per minute, tokens per minute and requests per day, and reset at midnight Pacific. The numbers are only shown in Google AI Studio. Developer-forum posts report free-tier daily limits as low as 20 requests for a Flash model and 500 for a Flash-Lite model (`gemini-3.5-flash-lite` was named), and Google staff describe the free tier as unstable. If the strong model really allows about 20 calls a day, the design is one strong call per company and quarter set, cached for good.
- **Groq:** limits are per organisation and shown in the console; no per-model free numbers were found. The docs show a sample of 14,400 requests a day and 18,000 tokens a minute, which is an example, not a promise.
- **Tavily:** free plan is 1,000 credits a month. A basic search costs 1 credit and an advanced search 2. The API can choose "advanced" by itself, so always send `search_depth="basic"`.

When keys exist: list the models the key can use, make one tiny call to the cheap and strong candidates, and put the chosen names in `.env`. Record them here.

## Re-running the probes

- **Laptop:** from `backend/`, `python -m probes.run_probes [SYMBOL ...]` (default RELIANCE, KAYNES, BAJFINANCE, CDSL) prints a table and writes `probes/out/report.json`. The three CDSL failures in the BSE rows are the expected "no BSE scrip" result.
- **Render:** `GET /debug/sources?symbol=RELIANCE` with the header `X-Admin-Token: <ADMIN_TOKEN>` runs the same probes on the server. It is temporary and admin-only; see [deploy.md](deploy.md). Paste the JSON into the Render column.
- **GitHub Actions:** needs the `workflow` scope on the GitHub login. Then a manual `workflow_dispatch` workflow can run `python -m probes.run_probes`.

## What this means for the build

1. **Run the pipeline on the laptop for now** and commit the JSON it writes. Both exchanges are only proven from a home connection, and Indian exchange sites often refuse datacenter IPs. Render and GitHub Actions have to be tested before anything depends on them.
2. **BSE first, NSE second.** BSE gives a category and subcategory, which Tier 0 rules can use. NSE needs no code mapping and is the only feed for NSE-only issuers such as CDSL. For an unseen ticker, resolve it, use BSE if there is a scrip code, otherwise NSE.
3. **Classification needs the subject text**, not only the category: `General` is 28% of rows and transcripts hide under `Analyst / Investor Meet`.
4. **Results extraction is verify-then-compute:** page selection, model extraction to JSON, a verbatim check per number, deltas in code, a Yahoo cross-check that tolerates restatements and attribution differences.
5. **LLM spend must be tiny and cached.** Treat the strong model as scarce.
6. **Annual reports need their own size cap and a section filter.**
