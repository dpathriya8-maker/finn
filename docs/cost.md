# LLM cost

Status: no LLM calls yet. The cards built so far (results figures, management changes) use no model at all, so they cost nothing per filing. Once the router in `backend/app/core/llm.py` exists, every call is logged (provider, model, tokens in and out, estimated cost, cache hit) and the summary is written here for the README.

| Tier | Used for | Model |
|---|---|---|
| 0 | Classification from BSE category/subcategory plus keyword rules | none |
| 1 | One-line summaries, results-number extraction to strict JSON, bio condensing, ambiguous classification | `LLM_CHEAP_MODEL` |
| 2 | Promise extraction and the promised-vs-delivered judgement | `LLM_STRONG_MODEL` |
| fallback | Provider quota exhausted or HTTP 429 | `LLM_FALLBACK_MODEL` |

Every LLM output is cached in SQLite under `sha256(doc_bytes + prompt_version + model)`, so the same input never costs twice.

Measured totals (calls, tokens, estimated cost, cache hit rate): to be generated.
