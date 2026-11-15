import { istDate, selectItems } from "@/lib/brief";
import { shortCategory } from "@/lib/labels";
import type { Settings } from "@/lib/settings";
import type { Brief, Item, Session } from "@/lib/types";

type Lines = Pick<Settings, "windowHours" | "priceMovePct" | "volumeMultiple" | "mutedSymbols">;

export type SignalAlert = {
  symbol: string;
  name: string;
  session: Session;
  reasons: ("price" | "volume")[];
  /** Down is bad (red), up is good (green), volume alone is a watch item (amber). */
  tone: "bad" | "watch" | "good";
  /** How far past the user's line it went: 1.0 is exactly on the line, 2.0 is twice as far. */
  severity: number;
  /** This company's stored sessions, oldest first, for the details table. */
  sessions: Session[];
};

const TONE_ORDER = { bad: 0, watch: 1, good: 2 } as const;

/** One price session per day of window: 24 hours is the latest session, 3 days the latest three, at most five stored. */
export function sessionCount(windowHours: number): number {
  return Math.min(5, Math.max(1, Math.round(windowHours / 24)));
}

/**
 * Unusual end-of-day moves. The pipeline stores raw numbers (percent move, volume against the 20-day
 * average) and this applies the user's lines, which is why moving a slider changes the result at once.
 * "More than": a move exactly on the line does not alert, as the brief words it.
 */
export function signalAlerts(brief: Brief, lines: Lines): SignalAlert[] {
  const muted = new Set(lines.mutedSymbols);
  const names = new Map(brief.companies.map((c) => [c.symbol, c.name]));
  const out: SignalAlert[] = [];

  for (const { symbol, sessions } of brief.signals) {
    if (muted.has(symbol)) continue;
    for (const session of sessions.slice(-sessionCount(lines.windowHours))) {
      const price = Math.abs(session.change_pct) > lines.priceMovePct;
      const volume = session.volume_ratio !== null && session.volume_ratio > lines.volumeMultiple;
      if (!price && !volume) continue;
      out.push({
        symbol,
        name: names.get(symbol) ?? symbol,
        session,
        reasons: [...(price ? (["price"] as const) : []), ...(volume ? (["volume"] as const) : [])],
        tone: price ? (session.change_pct < 0 ? "bad" : "good") : "watch",
        severity: Math.max(Math.abs(session.change_pct) / lines.priceMovePct, (session.volume_ratio ?? 0) / lines.volumeMultiple),
        sessions,
      });
    }
  }
  // Risks first (negativity bias), then the furthest past the line, then the most recent.
  return out.sort(
    (a, b) =>
      TONE_ORDER[a.tone] - TONE_ORDER[b.tone] ||
      b.severity - a.severity ||
      b.session.day.localeCompare(a.session.day),
  );
}

/** Filings in the categories the user asked to hear about, whether or not the Brief calls them routine. */
export function filingAlerts(
  brief: Brief,
  lines: Pick<Settings, "windowHours" | "alertCategories" | "mutedSymbols">,
): Item[] {
  return selectItems(brief, lines.windowHours, lines.mutedSymbols)
    .filter((item) => lines.alertCategories[item.category])
    .sort((a, b) => b.priority - a.priority || Date.parse(b.published_at) - Date.parse(a.published_at));
}

export function alertCount(brief: Brief, settings: Settings): number {
  return signalAlerts(brief, settings).length + filingAlerts(brief, settings).length;
}

/** "fell 5.3%" or "rose 5.3%". */
export function moveWords(changePct: number): string {
  return `${changePct < 0 ? "fell" : "rose"} ${Math.abs(changePct).toFixed(1)}%`;
}

/** "−6.1%" with a real minus sign, "+3.8%" for a rise. */
function signed(pct: number): string {
  return `${pct < 0 ? "−" : "+"}${Math.abs(pct).toFixed(1)}%`;
}

/**
 * Why a price or volume alert fired, in plain words and against the reader's own lines, one string per reason:
 * "Price −6.1% · your limit ±5%" and "Volume 3.2× the 20-day average · your limit 2×".
 */
export function signalReasons(alert: Pick<SignalAlert, "session" | "reasons">, lines: Pick<Settings, "priceMovePct" | "volumeMultiple">): string[] {
  const out: string[] = [];
  if (alert.reasons.includes("price")) out.push(`Price ${signed(alert.session.change_pct)} · your limit ±${lines.priceMovePct}%`);
  if (alert.reasons.includes("volume")) out.push(`Volume ${(alert.session.volume_ratio ?? 0).toFixed(1)}× the 20-day average · your limit ${lines.volumeMultiple}×`);
  return out;
}

/**
 * Does a filing explain the move? Real data only: the company's material (not routine) filings of the same India calendar day as
 * the session. "A filing came out today: Results" if that day is the day the data was made, "... that day: ..." for an older session,
 * and "No filing explains this move" if there is none. Several filings are named by their short labels, most important first.
 */
export function filingNote(symbol: string, day: string, items: readonly Item[], generatedAt: string): string {
  const same = items
    .filter((item) => item.symbol === symbol && !item.routine && istDate(Date.parse(item.published_at)) === day)
    .sort((a, b) => b.priority - a.priority);
  if (same.length === 0) return "No filing explains this move";
  const labels = [...new Set(same.map((item) => shortCategory(item)))];
  const when = istDate(Date.parse(generatedAt)) === day ? "today" : "that day";
  return `A filing came out ${when}: ${labels.slice(0, 2).join(", ")}${labels.length > 2 ? ` and ${labels.length - 2} more` : ""}`;
}
