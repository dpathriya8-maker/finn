"use client";

import { useId, useMemo, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { useAllBriefPrices } from "@/components/brief/PricesContext";
import { shortName } from "@/lib/headline";
import { arrowInr, arrowInrPct, directionOf, formatInr, plainPct, quoteOf, summarize, useInvested, type Direction, type Summary } from "@/lib/invested";
import { priceView } from "@/lib/prices";
import type { BriefCompany } from "@/lib/types";

const TEXT: Record<Direction, string> = { good: "text-good", bad: "text-bad", flat: "text-ink" };

function Figure({ label, children, tone = "flat" }: { label: string; children: React.ReactNode; tone?: Direction }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className={`mt-0.5 break-words text-base font-semibold tabular-nums leading-snug ${TEXT[tone]}`}>{children}</dd>
    </div>
  );
}

/** One company in the breakdown: its profit or loss (or, with no buy price, today's move), then what it is worth and its share. */
function Row({ row, name, basis }: { row: Summary["rows"][number]; name: string; basis: Summary["weightBasis"] }) {
  const pnlTone = row.pnl === null ? "flat" : directionOf(row.pnl);
  return (
    <li className="min-w-0 px-4 py-2.5">
      <div className="flex min-w-0 items-baseline justify-between gap-3">
        <span className="min-w-0 truncate text-sm font-medium">
          {name}
          {row.sample && <span className="ml-1.5 rounded bg-backdrop px-1.5 text-xs font-medium text-ink-soft">Sample</span>}
        </span>
        <span className={`shrink-0 text-sm font-semibold tabular-nums ${TEXT[pnlTone]}`}>
          {row.pnl !== null && row.pnlPct !== null ? arrowInrPct(row.pnl, row.pnlPct) : "No buy price"}
        </span>
      </div>
      <p className="mt-0.5 flex min-w-0 flex-wrap items-baseline gap-x-2 text-xs tabular-nums text-ink-faint">
        {row.value !== null ? <span>Worth {formatInr(row.value)}</span> : <span>Invested {formatInr(row.amount)}</span>}
        <span>
          {plainPct(row.weight)} of {basis === "value" ? "value" : "invested"}
        </span>
        {row.today !== null && (
          <span className={TEXT[directionOf(row.today)]}>{directionOf(row.today) === "flat" ? "flat today" : `${arrowInr(row.today)} today`}</span>
        )}
      </p>
    </li>
  );
}

/**
 * The reader's whole portfolio in four numbers, shown only when at least one amount is set: invested, worth now, overall profit
 * or loss, and today's move. Tap for a per-company breakdown, biggest loss first. Every figure is worked out in `lib/invested.ts`
 * from the amounts and buy prices the reader typed and the latest real closes. Without a buy price a company has no profit or
 * loss, so "worth now" and "overall" cover only the companies that do, and the card says how many.
 */
export function PortfolioSummary({ companies }: { companies: readonly BriefCompany[] }) {
  const holdings = useInvested();
  const { sessions, generatedAt } = useAllBriefPrices();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const symbols = useMemo(() => companies.map((c) => c.symbol), [companies]);
  const summary = useMemo(
    () => summarize(holdings, symbols, (symbol) => quoteOf(priceView(sessions.get(symbol), generatedAt))),
    [holdings, symbols, sessions, generatedAt],
  );
  if (!summary) return null;
  const names = new Map(companies.map((c) => [c.symbol, shortName(c.name)]));

  const partial = summary.priced < summary.count;
  const scope = partial ? ` (${summary.priced} of ${summary.count})` : "";
  const overallTone = summary.overall === null ? "flat" : directionOf(summary.overall);
  const todayTone = summary.today === null ? "flat" : directionOf(summary.today);

  return (
    <section aria-label="My portfolio" className="mb-4 min-w-0 overflow-hidden rounded-2xl border border-line bg-surface" data-testid="portfolio-summary">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="block min-h-11 w-full min-w-0 px-4 py-3 text-left"
      >
        <span className="flex min-w-0 items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <span className="text-sm font-semibold">My portfolio</span>
            {summary.sampleCount > 0 && <span className="shrink-0 rounded bg-backdrop px-1.5 py-0.5 text-xs font-medium text-ink-soft">Sample holdings</span>}
          </span>
          <Chevron open={open} />
        </span>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
          <Figure label="Total invested">{formatInr(summary.invested)}</Figure>
          <Figure label={`Current value${scope}`}>{summary.value === null ? "Add a buy price" : formatInr(summary.value)}</Figure>
          <Figure label={`Overall${scope}`} tone={overallTone}>
            {summary.overall === null || summary.overallPct === null ? "Add a buy price" : arrowInrPct(summary.overall, summary.overallPct)}
          </Figure>
          <Figure label="Today" tone={todayTone}>
            {summary.today === null ? "No price yet" : directionOf(summary.today) === "flat" ? "No change" : arrowInr(summary.today)}
          </Figure>
        </dl>
      </button>

      {open && (
        <div id={panelId} className="min-w-0 border-t border-line">
          <h3 className="px-4 pt-3 text-xs font-semibold text-ink-soft">By company, biggest loss first</h3>
          <ul className="mt-1 divide-y divide-line">
            {summary.rows.map((row) => (
              <Row key={row.symbol} row={row} name={names.get(row.symbol) ?? row.symbol} basis={summary.weightBasis} />
            ))}
          </ul>
          {partial && (
            <p className="px-4 pt-2 text-xs leading-5 text-ink-faint">
              Current value and overall cover the {summary.priced} of {summary.count} holdings that have a buy price. For the rest, today&apos;s move uses your amount as today&apos;s value.
            </p>
          )}
        </div>
      )}
      <p className="px-4 pb-3 pt-2 text-xs leading-5 text-ink-faint">
        {summary.sampleCount > 0 ? "Sample numbers, not yours. " : "From the amounts you entered under You. "}For understanding only, not advice.
      </p>
    </section>
  );
}
