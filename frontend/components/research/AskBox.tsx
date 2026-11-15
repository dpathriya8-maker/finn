"use client";

import { useState } from "react";
import { askDocuments } from "@/lib/researchApi";
import { pageLink, type AskResult } from "@/lib/research";

const MAX = 300;

type View =
  | { kind: "idle" }
  | { kind: "asking" }
  | { kind: "result"; result: AskResult }
  | { kind: "refused"; message: string }
  | { kind: "asleep" };

function Source({ result, doc, page }: { result: AskResult; doc: string; page: number }) {
  const found = result.documents.find((d) => d.id === doc);
  const link = found ? pageLink(found, page) : null;
  const label = found ? `${found.period ?? found.title}, page ${page}` : `page ${page}`;
  return (
    <span className="flex flex-wrap items-center gap-x-2 text-xs text-ink-faint">
      <span>{found?.title ? `${found.title}, page ${page}` : label}</span>
      {link && (
        <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center font-medium text-ink-soft underline underline-offset-2">
          Open at that page
        </a>
      )}
    </span>
  );
}

function Result({ result }: { result: AskResult }) {
  if (result.status === "not_found") {
    return (
      <div role="status" className="rounded-2xl border border-line bg-surface p-4">
        <p className="text-base font-semibold">Not found in the documents</p>
        <p className="mt-1 text-sm leading-6 text-ink-soft">The filings FINN has read do not say. It does not guess, and it does not use anything outside them.</p>
      </div>
    );
  }
  return (
    <div role="status" className="space-y-3">
      {result.status === "answered" && result.answer && <p className="text-base font-semibold leading-snug">{result.answer}</p>}
      <p className="text-xs leading-5 text-ink-faint">{result.note}</p>
      {(result.status === "answered" ? result.citations.map((c) => ({ doc: c.doc, page: c.page, text: c.quote })) : result.passages).map((item) => (
        <figure key={`${item.doc}-${item.page}-${item.text.slice(0, 20)}`}>
          <blockquote className="border-l-2 border-line pl-3 text-sm leading-6">“{item.text}”</blockquote>
          <figcaption className="mt-1.5 pl-3">
            <Source result={result} doc={item.doc} page={item.page} />
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

/** Ask the documents: one question, answered only from the filings, with quotes, or "Not found in the documents". */
export function AskBox({ symbol, suggestions }: { symbol: string; suggestions: string[] }) {
  const [question, setQuestion] = useState("");
  const [view, setView] = useState<View>({ kind: "idle" });

  async function submit(text: string) {
    const q = text.trim();
    if (q.length < 4) return setView({ kind: "refused", message: "Ask a full question, for example “What did management say about capex?”" });
    setView({ kind: "asking" });
    const outcome = await askDocuments(symbol, q);
    if (outcome.kind === "result") setView({ kind: "result", result: outcome.result });
    else if (outcome.kind === "refused") setView({ kind: "refused", message: outcome.message });
    else setView({ kind: "asleep" });
  }

  return (
    <section aria-labelledby="ask-title" className="rounded-2xl border border-line bg-surface p-4">
      <h2 id="ask-title" className="text-sm font-semibold">
        Ask the documents
      </h2>
      <p className="mt-1 text-xs leading-5 text-ink-faint">Answered only from this company’s filings. If they do not say, you get “Not found in the documents”.</p>
      <form
        className="mt-3"
        onSubmit={(event) => {
          event.preventDefault();
          void submit(question);
        }}
      >
        <label htmlFor="ask" className="sr-only">
          Your question about {symbol}
        </label>
        <textarea
          id="ask"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={MAX}
          rows={2}
          placeholder="For example: What did management say about capex?"
          className="w-full resize-none rounded-xl border border-line bg-surface px-3 py-2.5 text-base leading-6 placeholder:text-ink-faint"
        />
        <div className="mt-1 flex items-center justify-between text-xs text-ink-faint">
          <span>
            {question.length}/{MAX}
          </span>
        </div>
        <button type="submit" disabled={view.kind === "asking"} className="mt-2 min-h-12 w-full rounded-full bg-accent-bg text-base font-semibold text-on-accent disabled:opacity-60">
          {view.kind === "asking" ? "Searching the filings…" : "Ask"}
        </button>
      </form>

      <ul className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <li key={s}>
            <button
              type="button"
              onClick={() => {
                setQuestion(s);
                void submit(s);
              }}
              className="min-h-11 rounded-full border border-line px-3 text-left text-xs font-medium text-ink-soft"
            >
              {s}
            </button>
          </li>
        ))}
      </ul>

      <div className="mt-4" aria-live="polite">
        {view.kind === "result" && <Result result={view.result} />}
        {view.kind === "refused" && (
          <p role="alert" className="text-sm leading-6 text-watch">
            {view.message}
          </p>
        )}
        {view.kind === "asleep" && (
          <p role="status" className="text-sm leading-6 text-watch">
            The research engine is asleep or not reachable. It wakes in about a minute. Try the question again shortly.
          </p>
        )}
      </div>
    </section>
  );
}
