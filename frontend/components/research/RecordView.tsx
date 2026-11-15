"use client";

import { useId, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { TONE } from "@/components/brief/tone";
import { AskBox } from "@/components/research/AskBox";
import { VerdictBar } from "@/components/ui/Charts";
import { Avatar, PriceLine } from "@/components/ui/Price";
import { GROUP_LIMIT } from "@/lib/brief";
import { shortName } from "@/lib/headline";
import { useCompanyPrices } from "@/lib/useSessions";
import {
  byDue,
  byId,
  dateLabel,
  deliveredText,
  documentsLine,
  dueText,
  excerpt,
  fewCallsText,
  fileSize,
  modelNote,
  numbersText,
  pageLink,
  promiseTopic,
  sayingLine,
  soWhat,
  sourceLabel,
  statementsByCall,
  statusLabel,
  STATUS_LOOK,
  tooFewCalls,
  type PromiseStatus,
  type ResearchDocument,
  type ResearchRecord,
  type Scorecard,
  type TrackedPromise,
} from "@/lib/research";

/** Bad news first (design rule 4): the order the verdict groups appear in. "Too early" is not here: it is one collapsed row. */
const GROUPS: PromiseStatus[] = ["Missed", "Not followed up", "Partly", "Kept"];
const STATEMENTS_PER_CALL = 3;

function Quote({ text, doc, page }: { text: string; doc: ResearchDocument | undefined; page: number }) {
  const link = pageLink(doc, page);
  return (
    <figure className="min-w-0">
      <blockquote className="break-words border-l-2 border-line pl-3 text-sm leading-6">“{text}”</blockquote>
      <figcaption className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 pl-3 text-xs text-ink-faint">
        <span>{sourceLabel(doc, page)}</span>
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-2">
            Open at page {page}
          </a>
        )}
      </figcaption>
    </figure>
  );
}

/**
 * A promise in three lines, like a filing in the Brief:
 *   line 1  verdict chip (colour and words) and the topic in a few words
 *   line 2  the promise as a short excerpt, word for word
 *   line 3  where it was said and where it was checked
 * The full quote with its page, what a later call says, the numbers and the reason are one tap away.
 */
function PromiseCard({ promise, docs, card }: { promise: TrackedPromise; docs: Map<string, ResearchDocument>; card: Scorecard | null }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const look = STATUS_LOOK[promise.verdict.status];
  const tone = TONE[look.tone];
  const evidence = promise.verdict.evidence;
  const due = dueText(promise);

  return (
    <article className="relative min-w-0 overflow-hidden rounded-2xl border border-line bg-surface">
      <div className={`border-l-4 ${look.tone === "neutral" ? "border-l-transparent" : tone.border}`}>
        <button type="button" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((v) => !v)} className="block min-h-11 w-full min-w-0 px-3 py-2.5 text-left">
          <span className="flex min-w-0 items-center gap-2 text-xs">
            <span className={`shrink-0 whitespace-nowrap rounded px-1.5 py-0.5 font-semibold ${tone.chip || "bg-line text-ink-soft"}`}>{statusLabel(promise.verdict)}</span>
            <span className="min-w-0 flex-1 truncate font-medium text-ink-soft">{promiseTopic(promise)}</span>
            <span className="shrink-0 text-ink-faint">
              <Chevron open={open} />
            </span>
          </span>
          <span className="mt-1.5 line-clamp-2 break-words text-[0.9375rem] font-semibold leading-snug">“{excerpt(promise.quote, 80)}”</span>
          <span className="mt-1 block truncate text-xs text-ink-faint">{sayingLine(promise, docs, card)}</span>
        </button>

        {open && (
          <div id={panelId} className="min-w-0 space-y-3 border-t border-line px-3 py-3">
            <Quote text={promise.quote} doc={docs.get(promise.doc)} page={promise.page} />
            {promise.what && <p className="break-words text-xs leading-5 text-ink-faint">What was promised: {promise.what}{due ? ` · due ${due}` : ""}</p>}
            {promise.verdict.reason && <p className="break-words text-sm leading-6 text-ink-soft">{promise.verdict.reason}</p>}
            {promise.verdict.numbers && !promise.verdict.reason.includes("of the promise") && (
              <p className="text-xs leading-5 tabular-nums text-ink-faint">{numbersText(promise.verdict.numbers)}</p>
            )}
            {evidence.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold text-ink-soft">What a later call says</p>
                {evidence.map((e) => (
                  <Quote key={`${e.doc}-${e.page}-${e.quote.slice(0, 20)}`} text={e.quote} doc={docs.get(e.doc)} page={e.page} />
                ))}
              </div>
            )}
            {promise.verdict.downgraded && (
              <p className="text-xs leading-5 text-ink-faint">The model gave a verdict that no quote from a later call supports, so it is shown as “{promise.verdict.status}”.</p>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

/** One verdict group: at most five promises, the rest one tap away. */
function PromiseGroup({ status, items, docs, card }: { status: PromiseStatus; items: TrackedPromise[]; docs: Map<string, ResearchDocument>; card: Scorecard | null }) {
  const [all, setAll] = useState(false);
  if (items.length === 0) return null;
  const shown = all ? items : items.slice(0, GROUP_LIMIT);
  const hidden = items.length - shown.length;
  const tone = TONE[STATUS_LOOK[status].tone];
  return (
    <div className="mt-5 first:mt-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${tone.chip || "bg-line text-ink-soft"}`}>{status}</span>
        <span className="text-xs font-normal text-ink-faint">{items.length}</span>
      </h3>
      <div className="mt-2 flex flex-col gap-2.5">
        {shown.map((p) => (
          <PromiseCard key={p.id} promise={p} docs={docs} card={card} />
        ))}
      </div>
      {hidden > 0 && (
        <button type="button" onClick={() => setAll(true)} className="mt-2.5 min-h-11 w-full rounded-full border border-line bg-surface text-sm font-medium text-accent">
          Show {hidden} more
        </button>
      )}
    </div>
  );
}

/** "Too early" promises as one collapsed row, like the routine row in the Brief; inside, soonest due first. */
function DueLater({ promises, docs, card }: { promises: TrackedPromise[]; docs: Map<string, ResearchDocument>; card: Scorecard | null }) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(false);
  const listId = useId();
  if (promises.length === 0) return null;
  const sorted = [...promises].sort(byDue);
  const shown = all ? sorted : sorted.slice(0, GROUP_LIMIT);
  return (
    <section className="mt-6 rounded-2xl border border-line bg-surface">
      <button type="button" aria-expanded={open} aria-controls={listId} onClick={() => setOpen((v) => !v)} className="flex min-h-14 w-full items-center justify-between gap-3 px-4 py-2 text-left">
        <span className="min-w-0">
          <span className="block text-sm font-semibold">
            {promises.length} {promises.length === 1 ? "promise is" : "promises are"} due later
          </span>
          <span className="block text-xs text-ink-faint">Tap to see them. Their dates have not come yet.</span>
        </span>
        <Chevron open={open} />
      </button>
      {open && (
        <div id={listId} className="border-t border-line p-3">
          <div className="flex flex-col gap-2.5">
            {shown.map((p) => (
              <PromiseCard key={p.id} promise={p} docs={docs} card={card} />
            ))}
          </div>
          {sorted.length > shown.length && (
            <button type="button" onClick={() => setAll(true)} className="mt-2.5 min-h-11 w-full rounded-full border border-line text-sm font-medium text-accent">
              Show {sorted.length - shown.length} more
            </button>
          )}
        </div>
      )}
    </section>
  );
}

/** The verdict first: how many of the promises that came due were delivered, the bar, one plain line, and who judged. */
function VerdictSummary({ record }: { record: ResearchRecord }) {
  const card = record.scorecard;
  if (!card) return null;
  return (
    <section aria-labelledby="score-title" className="rounded-2xl border border-line bg-surface p-4">
      <h2 id="score-title" className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
        Promise Tracker
      </h2>
      <p className="mt-1.5 text-xl font-semibold leading-snug tracking-tight">{deliveredText(card)}</p>
      <div className="mt-3">
        <VerdictBar card={card} />
      </div>
      <p className="mt-3 text-sm font-medium leading-6">{soWhat(card)}</p>
      <p className="mt-1 text-xs leading-5 text-ink-faint">{modelNote(record)}</p>
      <details className="mt-2 text-xs leading-5 text-ink-soft">
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-medium text-accent underline underline-offset-2">How this is counted</summary>
        <ul className="space-y-1.5 pb-1">
          {(["Missed", "Not followed up", "Partly", "Kept", "Too early"] as PromiseStatus[]).map((status) => (
            <li key={status}>
              <span className={`mr-1.5 rounded px-1.5 py-0.5 font-semibold ${TONE[STATUS_LOOK[status].tone].chip || "bg-line text-ink-soft"}`}>{status}</span>
              {STATUS_LOOK[status].meaning}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-ink-faint">
          Counted here from the verdicts below, not generated. “Delivered” is Kept plus Partly, out of Kept, Partly, Missed and Not followed up. Verdicts are given only after a promise’s date has passed
          {card.as_of ? ` (measured against the ${card.as_of_call ?? "latest"} call, ${dateLabel(card.as_of)})` : ""}, unless management itself says it has been pushed back or dropped.
          {card.no_deadline ? ` ${card.no_deadline} commitment${card.no_deadline === 1 ? "" : "s"} with no stated time frame ${card.no_deadline === 1 ? "is" : "are"} not tracked.` : ""}
        </p>
      </details>
    </section>
  );
}

/** What management said about the future, found by rules: collapsed, newest call first, three per call. */
function Statements({ record, docs }: { record: ResearchRecord; docs: Map<string, ResearchDocument> }) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const listId = useId();
  const groups = statementsByCall(record.statements);
  if (groups.length === 0) return null;
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);
  return (
    <section className="rounded-2xl border border-line bg-surface">
      <button type="button" aria-expanded={open} aria-controls={listId} onClick={() => setOpen((v) => !v)} className="flex min-h-14 w-full items-center justify-between gap-3 px-4 py-2 text-left">
        <span className="min-w-0">
          <span className="block text-sm font-semibold">What management said about the future</span>
          <span className="block text-xs text-ink-faint">
            {total} {total === 1 ? "sentence" : "sentences"} across {groups.length} {groups.length === 1 ? "call" : "calls"}, found by rules, word for word
          </span>
        </span>
        <Chevron open={open} />
      </button>
      {open && (
        <div id={listId} className="space-y-4 border-t border-line p-4">
          {groups.map((group) => {
            const all = expanded.has(group.doc);
            const shown = all ? group.items : group.items.slice(0, STATEMENTS_PER_CALL);
            return (
              <div key={group.doc}>
                <h3 className="text-xs font-semibold text-ink-soft">{group.quarter} call</h3>
                <ul className="mt-2 space-y-3">
                  {shown.map((s) => (
                    <li key={`${s.doc}-${s.page}-${s.text.slice(0, 24)}`}>
                      <Quote text={s.text} doc={docs.get(s.doc)} page={s.page} />
                    </li>
                  ))}
                </ul>
                {group.items.length > shown.length && (
                  <button type="button" onClick={() => setExpanded(new Set([...expanded, group.doc]))} className="mt-2 min-h-11 text-xs font-medium text-accent underline underline-offset-2">
                    Show {group.items.length - shown.length} more from this call
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
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
      <ul className="mt-2 divide-y divide-line rounded-2xl border border-line bg-surface">
        {record.documents.map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <span className="min-w-0">
              <span className="block break-words text-sm font-medium">{d.title}</span>
              <span className="block text-xs text-ink-faint">
                Filed {dateLabel(d.date)} · {d.pages} pages · {fileSize(d.bytes)}
              </span>
            </span>
            <a href={d.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 shrink-0 items-center rounded-full border border-line px-4 text-sm font-medium text-accent">
              Open
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A researched company: the verdict first, then the promises it rests on (bad news first), then what was said, then a way to question the documents. */
export function RecordView({ record }: { record: ResearchRecord; source: "shipped" | "live" }) {
  const docs = byId(record.documents);
  const noDocuments = record.status === "no_documents";
  const prices = useCompanyPrices(record.symbol);
  const card = record.scorecard;
  const byStatus = (status: PromiseStatus) => record.promises.filter((p) => p.verdict.status === status).sort((a, b) => a.doc.localeCompare(b.doc) || a.page - b.page);
  const dueLater = record.promises.filter((p) => p.verdict.status === "Too early");
  const hasJudged = GROUPS.some((s) => byStatus(s).length > 0);

  return (
    <div className="space-y-6">
      <header className="min-w-0">
        <div className="flex min-w-0 items-center gap-2.5">
          <Avatar symbol={record.symbol} name={record.name} size={40} />
          <h2 className="min-w-0 flex-1 truncate text-lg font-semibold leading-tight tracking-tight">{shortName(record.name)}</h2>
          <PriceLine sessions={prices.sessions} generatedAt={prices.generatedAt} />
        </div>
        <p className="mt-2 text-xs leading-5 text-ink-faint">{noDocuments ? "Nothing to read yet" : documentsLine(record)}</p>
      </header>

      {noDocuments && (
        <section className="rounded-2xl border border-line bg-surface p-5" role="status">
          <h3 className="text-base font-medium text-watch">Nothing to read</h3>
          <p className="mt-1 text-sm leading-6 text-ink-soft">{record.reason}</p>
        </section>
      )}

      {!noDocuments && tooFewCalls(record) && (
        <section className="rounded-2xl border border-line border-l-4 border-l-watch bg-surface p-4" role="note">
          <h3 className="text-sm font-semibold">{fewCallsText(record)}</h3>
          <p className="mt-1 text-sm leading-6 text-ink-soft">A promise is judged by what a later call says, so FINN needs at least two. What management said is below, word for word with its page.</p>
        </section>
      )}

      {record.status === "statements_only" && !tooFewCalls(record) && (
        <section className="rounded-2xl bg-watch-bg p-4 text-watch" role="note">
          <h3 className="text-sm font-semibold">No verdict yet</h3>
          <p className="mt-1 text-sm leading-6">
            FINN has read these filings, but no AI model has been run on them, so it cannot yet say which promises were kept. {record.model.reason ? `(${record.model.reason}) ` : ""}
            What management said is below, found by rules and shown word for word with its source page.
          </p>
        </section>
      )}

      <VerdictSummary record={record} />

      {record.promises.length > 0 && (
        <section aria-labelledby="promises-title">
          <h2 id="promises-title" className="text-lg font-semibold tracking-tight">
            Promised, and what happened
          </h2>
          <p className="mt-0.5 text-xs leading-5 text-ink-faint">What was missed comes first. Every quote is word for word from the page shown.</p>
          {hasJudged ? (
            GROUPS.map((status) => <PromiseGroup key={status} status={status} items={byStatus(status)} docs={docs} card={card} />)
          ) : (
            <p className="mt-3 text-sm leading-6 text-ink-soft">None of these promises has come due yet.</p>
          )}
          <DueLater promises={dueLater} docs={docs} card={card} />
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

const SUGGESTIONS = ["What did they say about margins?", "What risks did they mention?", "What is their capex plan?"];
