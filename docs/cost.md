# LLM cost

Status: **measured on 15 Nov 2026, all on Gemini's free tier, $0.** The router in `backend/app/core/llm.py` logs every call (provider, model, tokens in and out, estimated cost if a price is set, cache hit) to `backend/.cache/llm_calls.jsonl`, never the prompt or the key; `python -m app.core.llm` prints the table. The cards (results figures, management changes), the documents, the statements found by rule and the retrieval use no model at all, so they cost nothing per filing.

What calls a model: promise extraction (one cheap-tier call per transcript, about 14 short excerpts each), the verdicts (one strong-tier call per older transcript), and "Ask the documents" (one cheap-tier call per question, six short excerpts). Every answer is cached by its input, the prompt version and the model, so asking again costs nothing. Since the second run (below) the verdict call is made once per commitment, and every decided verdict gets one more, second-reading call.

| Tier | Used for | Model |
|---|---|---|
| 0 | Classification from BSE category/subcategory plus keyword rules | none |
| 1 | One-line summaries, results-number extraction to strict JSON, bio condensing, ambiguous classification | `LLM_CHEAP_MODEL` |
| 2 | Promise extraction and the promised-vs-delivered judgement | `LLM_STRONG_MODEL` |
| fallback | Provider quota exhausted or HTTP 429 | `LLM_FALLBACK_MODEL` |

Every LLM output is cached in SQLite under `sha256(doc_bytes + prompt_version + model)`, so the same input never costs twice.

## Measured: the first run, Promise Tracker for 3 companies (Bajaj Finance, Asian Paints, Naukri)

HAL has one transcript in the window, so it has statements and no verdicts (nothing later to judge against).

| Model | Used for | Fresh calls | Tokens in | Tokens out |
|---|---|---|---|---|
| `gemini-3.5-flash-lite` | promise extraction, one call per transcript | 12 | 32,222 | 4,917 |
| `gemini-3.5-flash` | verdicts against later calls | 9 | 24,418 | 3,844 |
| `gemini-3.5-flash-lite` | verdicts, as the fallback for 4 strong calls that failed | 4 | 14,209 | 2,022 |
| | **Total** | **25 successful (+4 failed)** | **70,849** | **10,783** |

- A rebuild that changes nothing is free: a second run answered 17 calls from the cache (12 extraction, 5 verdicts).
- About 5 successful calls and about 19,000 tokens in per company for the whole tracker; 54 verdicts in total.
- Cost on the free tier: **$0**. No list price is set in `config/llm_prices.json` (prices change, none is guessed), so there is no dollar estimate.
- "Ask the documents" was not part of this run, so its per-question cost is not measured yet.

## Measured: the whole session, 15 Nov 2026 (two live runs and their re-runs)

Everything the project called a model for, from the log: **210 successful calls, 75 of them answered from the cache (no tokens), and 31 failed** (almost all HTTP 429: a free-tier limit, then the router fell back to the cheap model).

| Model | Used for | Fresh calls | Tokens in | Tokens out |
|---|---|---|---|---|
| `gemini-3.5-flash-lite` | promise extraction, one call per transcript | 28 | 78,377 | 11,214 |
| `gemini-3.5-flash-lite` | judging one commitment against later calls (also the fallback for the strong model) | 79 | 219,931 | 15,367 |
| `gemini-3.5-flash-lite` | second reading of each decided verdict | 7 | 4,886 | 597 |
| `gemini-3.5-flash-lite` | "Ask the documents", 5 questions | 5 | 5,569 | 1,037 |
| `gemini-3.5-flash` | judging (strong tier), before its free daily quota ran out | 16 | 58,607 | 7,076 |
| | **Total fresh** | **135** | **367,370** | **35,291** |

- Cost on the free tier: **$0**. No list price is set in `config/llm_prices.json` (prices change, none is guessed), so there is no dollar estimate.
- **The strong model's free quota is 20 requests a day** (`gemini-3.5-flash`), and it was used up by re-runs on the same day. After that every judging call fell to `gemini-3.5-flash-lite`, so the verdicts in the shipped records were made by the lite model. The records say which model answered. The router now stops retrying a model that has said its daily quota is gone (it is skipped for an hour), and waits for the time Gemini's own `retryDelay` gives.
- The re-runs cost far more than the first run because the prompt changed several times (each prompt version is a new cache key): 5 versions of the judging prompt. A re-run with an unchanged prompt costs nothing (the first run: 17 of 17 calls from the cache).
- A "Not due yet" promise costs no model call unless a later excerpt has a word of a slip, and a promise nothing later mentions costs none either.

## What went wrong, and the fix

The first run had 4 of the strong model's verdict calls fail with "reply cut off at the token limit": Gemini 3.x counts its thinking tokens against the output cap, and the thinking used it up before the JSON was written. The router fell back to the cheap model, so nothing was lost, but the strong tier was not doing the work. Fix: Gemini requests now set `thinkingLevel: low`, the verdict cap went from 3,000 to 6,000, and thinking tokens are counted in "tokens out" so the table does not understate. The re-run had no failures.
