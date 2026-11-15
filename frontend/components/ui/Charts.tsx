import { formatCrore } from "@/lib/results";
import type { ResultsCard, CardMetric } from "@/lib/types";
import type { Scorecard } from "@/lib/research";

// ------------------------------------------------------------------------------------------------ verdicts
const SEGMENTS = [
  { key: "missed", label: "Missed", bar: "bg-bad", dot: "bg-bad" },
  { key: "not_followed_up", label: "Not followed up", bar: "border-2 border-watch bg-transparent", dot: "border-2 border-watch" },
  { key: "partly", label: "Partly", bar: "bg-watch", dot: "bg-watch" },
  { key: "kept", label: "Kept", bar: "bg-good", dot: "bg-good" },
  { key: "too_early", label: "Too early", bar: "bg-ink-faint/40", dot: "bg-ink-faint/40" },
] as const;

/** The counts of a Promise Tracker as one stacked bar with a legend. Colour is the verdict; the numbers are written out too. */
export function VerdictBar({ card, legend = true, thin = false }: { card: Scorecard; legend?: boolean; thin?: boolean }) {
  const counts = SEGMENTS.map((s) => ({ ...s, n: (card[s.key as keyof Scorecard] as number | undefined) ?? 0 }));
  const total = counts.reduce((sum, c) => sum + c.n, 0);
  if (total === 0) return null;
  const summary = counts.filter((c) => c.n > 0).map((c) => `${c.label} ${c.n}`).join(", ");
  return (
    <div>
      <div role="img" aria-label={`Verdicts: ${summary}`} className={`flex w-full gap-0.5 overflow-hidden rounded-full ${thin ? "h-2" : "h-3"}`}>
        {counts
          .filter((c) => c.n > 0)
          .map((c) => (
            <span key={c.key} className={`block h-full ${c.bar}`} style={{ flexGrow: c.n, flexBasis: 0 }} />
          ))}
      </div>
      {legend && (
        <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-soft">
          {counts
            .filter((c) => c.n > 0)
            .map((c) => (
              <li key={c.key} className="inline-flex items-center gap-1.5">
                <span className={`inline-block size-2.5 rounded-full ${c.dot}`} aria-hidden="true" />
                {c.label} <span className="font-semibold tabular-nums text-ink">{c.n}</span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ results
type Ok = Extract<ResultsCard, { status: "ok" | "partial" }>;

function bars(metric: CardMetric) {
  const { year_ago: a, previous: b, current: c } = metric;
  if (a === null || b === null || c === null) return null;
  return [
    { label: "Year ago", value: a, now: false },
    { label: "Last qtr", value: b, now: false },
    { label: "This qtr", value: c, now: true },
  ];
}

function BarGroup({ metric }: { metric: CardMetric }) {
  const data = bars(metric);
  if (!data) return null;
  const top = Math.max(...data.map((d) => Math.abs(d.value)), 1);
  const yoy = metric.yoy_pct;
  const nowClass = yoy === null ? "bg-ink-soft" : yoy >= 0 ? "bg-good" : "bg-bad";
  const summary = data.map((d) => `${d.label} ${formatCrore(d.value)}`).join(", ");
  return (
    <figure className="min-w-0 flex-1">
      <figcaption className="text-xs font-medium text-ink-soft">{metric.label}</figcaption>
      <div role="img" aria-label={`${metric.label}, ₹ crore: ${summary}`} className="mt-1.5 flex h-20 items-end gap-1.5">
        {data.map((d) => (
          <div key={d.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end">
            <span className="text-[10px] leading-3 tabular-nums text-ink-soft">{formatCrore(d.value)}</span>
            <span
              className={`mt-0.5 block w-full rounded-t ${d.now ? nowClass : "bg-ink-faint/35"} ${d.value < 0 ? "opacity-60" : ""}`}
              style={{ height: `${Math.max(4, (Math.abs(d.value) / top) * 52)}px` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5 text-[10px] leading-3 text-ink-faint">
        {data.map((d) => (
          <span key={d.label} className="min-w-0 flex-1 text-center">
            {d.label}
          </span>
        ))}
      </div>
    </figure>
  );
}

/** Revenue and profit over three periods: the same quarter a year ago, last quarter, this quarter, from the figures read in the filing. */
export function MetricBars({ card }: { card: Ok }) {
  const revenue = card.metrics.find((m) => m.key === "revenue");
  const profit = card.metrics.find((m) => m.key === "pat") ?? card.metrics.find((m) => m.key === "pat_owners");
  const shown = [revenue, profit].filter((m): m is CardMetric => !!m && bars(m) !== null);
  if (shown.length === 0) return null;
  return (
    <div className="mt-3 flex gap-4" aria-label="Revenue and profit over three periods">
      {shown.map((m) => (
        <BarGroup key={m.key} metric={m} />
      ))}
    </div>
  );
}
