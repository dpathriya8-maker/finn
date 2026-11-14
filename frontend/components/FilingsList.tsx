"use client";

import { formatIst } from "@/lib/format";
import { useBrief } from "@/lib/useBrief";

const SHOWN = 8;

/** Step 4: proof that the real pipeline data reaches the app. The Morning Brief replaces this. */
export function FilingsList() {
  const state = useBrief();

  if (state.kind === "loading") {
    return <div className="h-40 animate-pulse rounded-2xl bg-line" aria-label="Loading filings" />;
  }
  if (state.kind === "error") {
    return (
      <section className="rounded-2xl border border-line p-5">
        <h2 className="text-base font-medium text-watch">Filings unavailable right now</h2>
        <p className="mt-1 text-sm text-ink-soft">The data file could not be loaded. Try again in a minute.</p>
      </section>
    );
  }

  const { brief } = state;
  const shown = brief.items.slice(0, SHOWN);
  return (
    <section aria-labelledby="latest-title">
      <h2 id="latest-title" className="text-base font-medium">
        Latest filings
      </h2>
      <p className="mt-0.5 text-sm text-ink-soft">
        {brief.items.length} filings from {brief.companies.length} companies in the last {brief.item_days} days
      </p>
      <ul className="mt-4 divide-y divide-line rounded-2xl border border-line">
        {shown.map((item) => (
          <li key={item.id} className="px-4 py-3">
            <div className="flex items-baseline justify-between gap-3 text-xs text-ink-faint">
              <span className="font-semibold text-ink-soft">{item.symbol}</span>
              <time dateTime={item.published_at}>{formatIst(item.published_at)}</time>
            </div>
            <p className="mt-1 text-sm leading-5">{item.subject}</p>
            {item.body && <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-ink-soft">{item.body}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
