"use client";

import { useState } from "react";
import { AskBox } from "@/components/research/AskBox";
import { TONE } from "@/components/brief/tone";
import {
  byId,
  dateLabel,
  deliveryText,
  dueText,
  fileSize,
  numbersText,
  orderPromises,
  pageLink,
  sourceLabel,
  statementsByCall,
  statusLabel,
  STATUS_LOOK,
  STATUS_ORDER,
  type PromiseStatus,
  type ResearchDocument,
  type ResearchRecord,
  type TrackedPromise,
} from "@/lib/research";

function Quote({ text, doc, page }: { text: string; doc: ResearchDocument | undefined; page: number }) {
  const link = pageLink(doc, page);
  return (
    <figure>
      <blockquote className="border-l-2 border-line pl-3 text-sm leading-6">“{text}”</blockquote>
      <figcaption className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 pl-3 text-xs text-ink-faint">
        <span>{sourceLabel(doc, page)}</span>
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center font-medium text-ink-soft underline underline-offset-2">
            Open at that page
          </a>
        )}
      </figcaption>
    </figure>
  );
}

function PromiseCard({ promise, docs }: { promise: TrackedPromise; docs: Map<string, ResearchDocument> }) {
  const [open, setOpen] = useState(false);
  const look = STATUS_LOOK[promise.verdict.status];
  const tone = TONE[look.tone];
  const evidence = promise.verdict.evidence;
  const due = dueText(promise);
  return (
    <article className={`rounded-2xl border border-l-4 border-line ${tone.border} bg-surface p-4`}>
      <p className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded px-1.5 py-0.5 font-semibold ${tone.chip || "bg-line text-ink-soft"}`}>{statusLabel(promise.verdict)}</span>
        <span className="text-ink-faint">Promised on the {promise.quarter} call</span>
        {due && <span className="text-ink-faint">· due {due}</span>}
      </p>
      <h3 className="mt-2 text-base font-semibold leading-snug">{promise.what || promise.quote}</h3>
      <div className="mt-3">
        <Quote text={promise.quote} doc={docs.get(promise.doc)} page={promise.page} />
      </div>
      {promise.verdict.reason && <p className="mt-3 text-sm leading-6 text-ink-soft">{promise.verdict.reason}</p>}
      {promise.verdict.numbers && <p className="mt-1 text-xs leading-5 text-ink-faint tabular-nums">{numbersText(promise.verdict.numbers)}</p>}
      {evidence.length > 0 && (
        <>
          <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="mt-2 inline-flex min-h-11 items-center text-xs font-medium text-ink-soft underline underline-offset-2">
            {open ? "Hide" : "Show"} what later calls say
          </button>
          {open && (
            <div className="space-y-3">
              {evidence.map((e) => (
                <Quote key={`${e.doc}-${e.page}-${e.quote.slice(0, 20)}`} text={e.quote} doc={docs.get(e.doc)} page={e.page} />
              ))}
            </div>
          )}
        </>
      )}
      {promise.verdict.downgraded && <p className="mt-2 text-xs leading-5 text-ink-faint">The model gave a verdict that no quote from a later call supports, so it is shown as “{promise.verdict.status}”.</p>}
    </article>
  );
}

function Scorecard({ record }: { record: ResearchRecord }) {
  const card = record.scorecard;
  if (!card) return null;
  const counts: Record<PromiseStatus, number> = {
    Missed: card.missed,
    "Not followed up": card.not_followed_up ?? 0,
    Partly: card.partly,
    Kept: card.kept,
    "Too early": card.too_early,
  };
  // Worry first, in rows of three then two (design rule 10: chunks of five at most).
  const cells = STATUS_ORDER.map((status, i) => ({ status, n: counts[status], span: i < 3 ? "col-span-2" : "col-span-3" }));
  return (
    <section aria-labelledby="score-title" className="rounded-2xl border border-line p-4">
      <h2 id="score-title" className="text-sm font-semibold">
        Promise Tracker
      </h2>
      <p className="mt-1 text-lg font-semibold leading-snug">{deliveryText(card)}</p>
      <ul className="mt-3 grid grid-cols-6 gap-2 text-center">
        {cells.map((cell) => (
          <li key={cell.status} className={`${cell.span} rounded-xl px-1 py-2 ${TONE[STATUS_LOOK[cell.status].tone].chip || "bg-line text-ink-soft"}`}>
            <span className="block text-xl font-semibold tabular-nums">{cell.n}</span>
            <span className="block text-xs font-medium">{cell.status}</span>
          </li>
        ))}
      </ul>
      <details className="mt-3 text-xs leading-5 text-ink-soft">
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-medium underline underline-offset-2">What the labels mean</summary>
        <ul className="space-y-1.5 pb-1">
          {STATUS_ORDER.map((status) => (
            <li key={status}>
              <span className={`mr-1.5 rounded px-1.5 py-0.5 font-semibold ${TONE[STATUS_LOOK[status].tone].chip || "bg-line text-ink-soft"}`}>{status}</span>
              {STATUS_LOOK[status].meaning}
            </li>
          ))}
        </ul>
      </details>
      <p className="mt-2 text-xs leading-5 text-ink-faint">
        Counted here from the verdicts below, not generated. Kept, Partly and Missed are given only after a promise’s date has passed
        {card.as_of ? ` (measured against the ${card.as_of_call ?? "latest"} call, ${dateLabel(card.as_of)})` : ""}, unless management itself says it has been pushed back or dropped.
        {card.no_deadline ? ` ${card.no_deadline} commitment${card.no_deadline === 1 ? "" : "s"} with no stated time frame ${card.no_deadline === 1 ? "is" : "are"} not tracked.` : ""}
      </p>
    </section>
  );
}

function Statements({ record, docs }: { record: ResearchRecord; docs: Map<string, ResearchDocument> }) {
  const groups = statementsByCall(record.statements);
  if (groups.length === 0) return null;
  const limited = record.status !== "ready";
  return (
    <section aria-labelledby="said-title">
      <h2 id="said-title" className="text-sm font-semibold">
        What management said about the future
      </h2>
      <p className="mt-1 text-xs leading-5 text-ink-faint">
        {limited ? "Found by rules, not by a model: sentences where management looks ahead and gives a number or a date. Shown word for word." : "Sentences where management looks ahead and gives a number or a date, found by rules. Shown word for word."}
      </p>
      <div className="mt-3 space-y-4">
        {groups.map((group) => (
          <div key={group.doc}>
            <h3 className="text-xs font-semibold text-ink-soft">{group.quarter} call</h3>
            <ul className="mt-2 space-y-3">
              {group.items.map((s) => (
                <li key={`${s.doc}-${s.page}-${s.text.slice(0, 24)}`} className="rounded-2xl border border-line p-4">
                  <Quote text={s.text} doc={docs.get(s.doc)} page={s.page} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function Documents({ record }: { record: ResearchRecord }) {
  if (record.documents.length === 0) return null;
  return (
    <section aria-labelledby="docs-title">
      <h2 id="docs-title" className="text-sm font-semibold">
        The documents read
      </h2>
      <ul className="mt-2 divide-y divide-line rounded-2xl border border-line">
        {record.documents.map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <span className="min-w-0">
              <span className="block text-sm font-medium">{d.title}</span>
              <span className="block text-xs text-ink-faint">
                Filed {dateLabel(d.date)} · {d.pages} pages · {fileSize(d.bytes)}
              </span>
            </span>
            <a href={d.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 shrink-0 items-center rounded-full border border-line px-4 text-sm font-medium">
              Open
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A researched company: the verdict first, then what it rests on, then the documents, then a way to question them. */
export function RecordView({ record, source }: { record: ResearchRecord; source: "shipped" | "live" }) {
  const docs = byId(record.documents);
  const promises = orderPromises(record.promises);
  const noDocuments = record.status === "no_documents";

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold tracking-tight">{record.name}</h2>
        <p className="mt-0.5 text-xs text-ink-faint">
          {record.symbol} · {noDocuments ? "nothing to read" : `${record.documents.length} filings read`} · {source === "shipped" ? "prepared in advance" : "read just now"}, {dateLabel(record.generated_at)}
        </p>
      </header>

      {noDocuments && (
        <section className="rounded-2xl border border-line p-5" role="status">
          <h3 className="text-base font-medium text-watch">Nothing to read</h3>
          <p className="mt-1 text-sm leading-6 text-ink-soft">{record.reason}</p>
        </section>
      )}

      {record.status === "statements_only" && (
        <section className="rounded-2xl bg-watch-bg p-4 text-watch" role="note">
          <h3 className="text-sm font-semibold">No verdict yet</h3>
          <p className="mt-1 text-sm leading-6">
            FINN has read these filings, but no AI model has been run on them, so it cannot yet say which promises were kept. {record.model.reason ? `(${record.model.reason}) ` : ""}
            What management said is below, found by rules and shown word for word with its source page.
          </p>
        </section>
      )}

      <Scorecard record={record} />

      {promises.length > 0 && (
        <section aria-labelledby="promises-title">
          <h2 id="promises-title" className="text-sm font-semibold">
            Promised, and what happened
          </h2>
          <p className="mt-1 text-xs leading-5 text-ink-faint">What was missed comes first. Every quote is word for word from the page shown.</p>
          <div className="mt-3 space-y-3">
            {promises.map((p) => (
              <PromiseCard key={p.id} promise={p} docs={docs} />
            ))}
          </div>
        </section>
      )}

      <Statements record={record} docs={docs} />

      {!noDocuments && <AskBox symbol={record.symbol} suggestions={SUGGESTIONS} />}

      <Documents record={record} />

      {record.warnings.length > 0 && (
        <section aria-labelledby="notes-title">
          <h2 id="notes-title" className="text-sm font-semibold">
            What could not be read
          </h2>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs leading-5 text-ink-soft">
            {record.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

const SUGGESTIONS = ["What did management say about capex?", "What is the margin outlook?", "What risks did management mention?"];
