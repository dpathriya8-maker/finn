# LLM cost

Status: **no model call has been made yet**, because there are no API keys. The router in `backend/app/core/llm.py` is built and tested against a fake transport; it logs every call (provider, model, tokens in and out, estimated cost if a price is set, cache hit) to `backend/.cache/llm_calls.jsonl`, never the prompt or the key. After a real run, `python -m app.core.llm` prints the table below as Markdown. The cards (results figures, management changes), the documents, the statements found by rule and the retrieval use no model at all, so they cost nothing per filing.

What will call a model once keys exist: promise extraction (one cheap-tier call per transcript, about 14 short excerpts each), the verdicts (one strong-tier call per older transcript), and "Ask the documents" (one cheap-tier call per question, six short excerpts). Roughly seven calls per company for the whole tracker; every answer is cached by its input, the prompt version and the model, so asking again costs nothing. Once the router in `backend/app/core/llm.py` exists, every call is logged (provider, model, tokens in and out, estimated cost, cache hit) and the summary is written here for the README.

| Tier | Used for | Model |
|---|---|---|
| 0 | Classification from BSE category/subcategory plus keyword rules | none |
| 1 | One-line summaries, results-number extraction to strict JSON, bio condensing, ambiguous classification | `LLM_CHEAP_MODEL` |
| 2 | Promise extraction and the promised-vs-delivered judgement | `LLM_STRONG_MODEL` |
| fallback | Provider quota exhausted or HTTP 429 | `LLM_FALLBACK_MODEL` |

Every LLM output is cached in SQLite under `sha256(doc_bytes + prompt_version + model)`, so the same input never costs twice.

## Measured: Promise Tracker for 3 companies (Bajaj Finance, Asian Paints, Naukri)

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

## What went wrong, and the fix

The first run had 4 of the strong model's verdict calls fail with "reply cut off at the token limit": Gemini 3.x counts its thinking tokens against the output cap, and the thinking used it up before the JSON was written. The router fell back to the cheap model, so nothing was lost, but the strong tier was not doing the work. Fix: Gemini requests now set `thinkingLevel: low`, the verdict cap went from 3,000 to 6,000, and thinking tokens are counted in "tokens out" so the table does not understate. The re-run had no failures.
