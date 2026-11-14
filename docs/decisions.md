# Decisions

Why FINN is built the way it is. D-entries were decided before the first line of code (they come from CLAUDE.md). S-entries are made while building. Newest at the bottom.

## Decided up front

| # | Area | Decision | Why |
|---|---|---|---|
| D1 | Product | PUSH is a **Morning Brief**: "N things that matter" cards grouped by priority, routine filings collapsed into one row, ending in "You're all caught up". | A finite, scannable brief beats an infinite feed; the user decides in three seconds whether to care. |
| D2 | Product | PULL is a **Promise Tracker** (last 4 quarters: Kept / Partly / Missed / Too early, each with quote, source document and page) plus an "Ask the documents" box. | It tests whether management delivers on what it says, and every claim is traceable. |
| D3 | Product | PULL answers only from annual reports and concall transcripts. No news, broker notes or outside model knowledge. "Not found in the documents" is a valid answer. | Grounding is the point; refusing to guess is a feature. |
| D4 | Product | Mobile-first, bottom nav (Brief, Alerts, Research, Settings), actions in the thumb zone. | Most use will be on a phone. |
| D5 | Product | Nothing is hard-coded to the demo companies; any NSE ticker must work. | Brief requirement. |
| D6 | Architecture | Push data is precomputed by a Python pipeline into static JSON (`frontend/public/data`) and served by Next.js on Vercel. | Instant load, no cold start. |
| D7 | Architecture | The pipeline stores raw metrics (volume ratio, % move); the client applies the user's thresholds. | Changing a threshold updates alerts instantly, with no recompute. |
| D8 | Architecture | FastAPI on Render is used only for PULL on tickers that are not precomputed, and for Ask-the-documents. The free tier sleeps, so the UI shows an honest "waking up research engine" state. | Keeps the backend off the critical path of the main screen. |
| D9 | Architecture | User settings live in localStorage. No accounts, no personal data. | Nothing to protect, nothing to leak. |
| D10 | LLM cost | Tier 0 uses no LLM: classification from BSE category/subcategory plus keyword rules. | Most filings can be classified for free. |
| D11 | LLM cost | Tier 1 (cheap model): one-line summaries, results-number extraction to strict JSON, bio condensing, ambiguous classification. Tier 2 (strong model): promise extraction and the promised-vs-delivered judgement only. | Spend the expensive model only where judgement is needed. |
| D12 | LLM cost | Model names come from env vars only (`LLM_CHEAP_MODEL`, `LLM_STRONG_MODEL`, `LLM_FALLBACK_MODEL`). A 429 triggers backoff, then the fallback provider. | Free-tier models and quotas change; that should not need a code change. |
| D13 | LLM cost | Every LLM output is cached in SQLite under `sha256(doc_bytes + prompt_version + model)`, and every call is logged (provider, model, tokens, estimated cost, cache hit) for `docs/cost.md`. Long PDFs are chunked and only relevant chunks are sent. | The same input never costs twice, and efficiency is graded. |
| D14 | Truth | The LLM never invents numbers. Figures are extracted with their source (document, page); QoQ/YoY deltas and margins are computed in code. | A wrong number in a finance app is worse than a missing one. |
| D15 | Truth | A quote is shown only if it appears verbatim (whitespace-normalised) in the source text. Document text is treated as data; instructions inside it are ignored. | Prevents fabricated quotes and prompt injection. |
| D16 | Truth | Extracted results numbers are cross-checked against an independent source where available (for example yfinance quarterly) and shown with a check or warning badge. | Lets the user see how far to trust a figure. |
| D17 | Truth | If a source fails, show the last cached data with its timestamp. Sample or cached data is always labelled. Never a blank screen, never silent fake data. | A demo that breaks is the worst outcome. |
| D18 | Security | Secrets live only in `.env` (gitignored) and the Vercel/Render dashboards; the frontend never holds a key. `.env.example` has names only. | The repo is public; keys must not leak. |
| D19 | Security | CORS allows only the Vercel domain and localhost; the backend is rate-limited per IP; fresh LLM research is capped per day (cached results are unlimited). | Protects the free quota. |
| D20 | Security | Ticker input must match `^[A-Z0-9&\-]{1,20}$`; outbound fetches go only to an allowlist of domains, with a 25 MB cap and timeouts; debug endpoints need an `ADMIN_TOKEN` header; dependencies are pinned. | Blocks SSRF, abuse and supply-chain drift. |
| D21 | Design | Every card answers "do I need to care?" headline-first. Progressive disclosure runs headline, numbers, source document and page. | The 3-second rule. |
| D22 | Design | Risks, misses and red flags rank above good news, and every pushed item shows why it ranked high. | Negativity bias, plus transparency. |
| D23 | Design | Colour carries meaning only (red bad, green good, amber watch). Money in ₹ Cr, percentages and ▲▼. Groups of at most 5. Smart defaults: 24 h window, 2× volume, ±5% move. | Fast, honest scanning. |
| D24 | Design | The user controls the window, thresholds and categories, and can mute a company. Plain language, one-line "so what", no filler. | Control reduces alert fatigue. |

## Made while building

| # | Step | Decision | Why |
|---|---|---|---|
| S1 | 1 | Config files are objects holding a named list (`{"companies": [...]}`, `{"categories": [...]}`) plus a `description`, not bare arrays. | JSON has no comments, and a wrapper lets us add fields later without breaking readers. |
| S2 | 1 | `size_bucket` is `large`, `mid` or `small`, taken from the lists in STEPS.md. It is a label, not a market-cap lookup. | Used for display and grouping only; the symbols themselves are verified in Step 3. |
| S3 | 1 | Categories have a stable snake_case `id` (`m_and_a` for M&A) and a display `label`. | Safe as keys in code and JSON. |
| S4 | 1 | Routine means insider trading, AGM/EGM, earnings-call logistics, postal ballot and investor meetings. `unclassified` is deliberately not routine: it ranks low but stays visible. | A filing we cannot classify might still matter, so it is never hidden in the collapsed row. |
| S5 | 1 | Alerts default to on only for litigation, pledging, results, management change, M&A, credit rating, fund raise and bonus/split. Nothing routine alerts by default (enforced by a test). | Alert fatigue. The user can switch any category on. |
| S6 | 1 | Category weights are base priorities (litigation 95, pledging 90, results 88, management change 85 and so on). The scorer may adjust per filing, for example a credit downgrade or a large miss. | A category cannot tell good news from bad; the filing can. |
| S7 | 1 | `scripts/check-secrets.sh` is plain bash plus grep. It runs as a pre-commit hook, has an `--all` mode for CI, never prints a match, supports an inline `secret-check:allow` marker, and fails closed if its export of the staged files is incomplete. | It must behave the same in Git Bash on Windows and on a Linux runner, and a scanner that silently says "clean" is worse than none. |
| S8 | 1 | Commits use the repo-local GitHub noreply address, not a personal email. | The repo is public. |
| S9 | 1 | `.gitattributes` forces LF line endings. | Shell scripts with CRLF break on Linux runners and in git hooks. |
