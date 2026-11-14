/** How a results card is shown. All the numbers arrive computed from the pipeline; this only formats them. */
import type { CardCheck, CardMetric, ResultsCard } from "@/lib/types";

type Readable = Exclude<ResultsCard, { status: "failed" }>;

/** Rupees crore with Indian digit grouping: "3,32,861" above a thousand, one decimal below, a real minus sign. */
export function formatCrore(value: number | null): string {
  if (value === null) return "—";
  const digits = Math.abs(value) >= 1000 ? 0 : 1;
  const text = new Intl.NumberFormat("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(value));
  return `${value < 0 && Number(text.replace(/,/g, "")) !== 0 ? "−" : ""}${text}`;
}

export type Delta = { text: string; direction: "up" | "down" | "flat" | "none" };

const PERCENT = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** "▲ 4.4%", "▼ 65.6%", or in words when a percentage means nothing: "▲ to profit", "▼ to loss". */
export function formatDelta(pct: number | null, swing: "turned profit" | "turned loss" | null): Delta {
  if (swing === "turned profit") return { text: "▲ to profit", direction: "up" };
  if (swing === "turned loss") return { text: "▼ to loss", direction: "down" };
  if (pct === null) return { text: "—", direction: "none" };
  const size = Math.round(Math.abs(pct) * 10) / 10;
  if (size === 0) return { text: "0.0%", direction: "flat" };
  return { text: `${pct > 0 ? "▲" : "▼"} ${PERCENT.format(size)}%`, direction: pct > 0 ? "up" : "down" };
}

export const DELTA_CLASS: Record<Delta["direction"], string> = {
  up: "text-good",
  down: "text-bad",
  flat: "text-ink-soft",
  none: "text-ink-faint",
};

const SHORT: Record<CardMetric["key"], { text: string; full?: string }> = {
  revenue: { text: "Revenue" },
  ebitda: { text: "EBITDA" },
  pbt: { text: "PBT", full: "Profit before tax" },
  pat: { text: "PAT", full: "Profit after tax" },
  pat_owners: { text: "Owners' PAT", full: "Profit after tax attributable to the owners of the company" },
};

export type MetricRow = {
  key: CardMetric["key"];
  text: string;
  full?: string;
  current: string;
  qoq: Delta;
  yoy: Delta;
  derived: string | null;
};

export function metricRows(card: Readable): MetricRow[] {
  return card.metrics.map((m) => ({
    key: m.key,
    text: SHORT[m.key]?.text ?? m.label,
    full: SHORT[m.key]?.full,
    current: formatCrore(m.current),
    qoq: formatDelta(m.qoq_pct, m.qoq_swing),
    yoy: formatDelta(m.yoy_pct, m.yoy_swing),
    derived: m.derived ?? null,
  }));
}

export type CheckView = { icon: string; title: string; tone: "good" | "watch" | "neutral"; lines: string[] };

const COMPARED: Record<string, string> = { revenue: "revenue", pbt: "PBT", pat: "PAT" };

/** Always icon plus words, so the badge never relies on colour alone. The lines say what the badge rests on. */
export function checkView(check: CardCheck): CheckView {
  const details = check.details ?? [];
  if (check.status === "ok") {
    const names = details.map((d) => COMPARED[d.metric] ?? d.metric);
    return { icon: "✓", title: "Matches Yahoo Finance", tone: "good", lines: names.length ? [`Same quarter; checked ${names.join(", ")}.`] : [] };
  }
  if (check.status === "differs") {
    const apart = details
      .filter((d) => !d.ok)
      .map((d) => `${COMPARED[d.metric] ?? d.metric}: filing ${formatCrore(d.filing)} against Yahoo ${formatCrore(d.yahoo)} crore (${d.diff_pct.toFixed(1)}% apart)`);
    return { icon: "⚠", title: "Differs from Yahoo Finance", tone: "watch", lines: [...apart, check.note] };
  }
  return { icon: "–", title: "Not cross-checked", tone: "neutral", lines: [check.note] };
}

export function basisLabel(basis: Readable["basis"]): string {
  return basis === "consolidated" ? "Consolidated" : basis === "standalone" ? "Standalone" : "Basis not stated";
}

const MARGIN_NAMES: [string, string][] = [
  ["ebitda", "EBITDA margin"],
  ["pbt", "PBT margin"],
  ["pat", "PAT margin"],
];

/** "EBITDA margin 12.6%, was 16.1% a year ago", for each margin the pipeline could compute. */
export function marginLines(card: Readable): string[] {
  const lines: string[] = [];
  for (const [key, name] of MARGIN_NAMES) {
    const m = card.margins[key];
    if (!m || m.current === null) continue;
    lines.push(m.year_ago === null ? `${name} ${m.current.toFixed(1)}%` : `${name} ${m.current.toFixed(1)}%, was ${m.year_ago.toFixed(1)}% a year ago`);
  }
  return lines;
}

/** The figures exactly as printed, for the "show me the filing's own numbers" disclosure. */
export function printedLine(metric: CardMetric): string {
  if (metric.printed.label === "computed") return "Computed here; nothing is printed for it.";
  const tokens = metric.printed.tokens.map((t) => t ?? "—").join("  ·  ");
  return `“${metric.printed.label}”, page ${metric.printed.page}: ${tokens}`;
}

export function pagesLabel(pages: number[]): string {
  if (pages.length === 0) return "";
  return pages.length === 1 ? `page ${pages[0]}` : `pages ${pages.join(", ")}`;
}

/** What the filing printed the unit as, when it was not crore, so the conversion is never hidden. */
export function unitNote(unit: string | null): string | null {
  if (!unit || unit === "crore") return null;
  return `The filing prints its figures in ₹ ${unit}; they are shown here in ₹ crore.`;
}
