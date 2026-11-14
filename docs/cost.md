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

Measured totals (calls, tokens, estimated cost, cache hit rate): to be generated.
