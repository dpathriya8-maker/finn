import type { Item } from "@/lib/types";

/**
 * One short word per category for the third line of a card. The full names in config/categories.json
 * ("Litigation & regulatory action") are too long for a phone, and a label is never cut off, so these stay short.
 * Keyed by category id, so any new category falls back to "Routine" or "Other" instead of breaking.
 */
const SHORT: Record<string, string> = {
  results: "Results",
  m_and_a: "M&A",
  management_change: "People",
  fund_raise: "Fund raise",
  litigation: "Legal",
  credit_rating: "Rating",
  dividend: "Dividend",
  pledging: "Pledge",
  bonus_split: "Bonus",
  capex: "Capex",
  press_release: "Update",
  agm_egm: "Meeting",
  postal_ballot: "Meeting",
  investor_meetings: "Meeting",
  earnings_call: "Meeting",
};

export function shortCategory(item: Pick<Item, "category" | "routine">): string {
  return SHORT[item.category] ?? (item.routine ? "Routine" : "Other");
}

// ------------------------------------------------------------------------------------------------ the short "why"
const MAX_WORDS = 8;

/** "Profit fell vs last year", "Revenue rose vs last year", "Profit turned to a loss": from the printed figures, never from a model. */
function resultsWhy(card: Item["card"]): string | null {
  if (!card || card.type !== "results" || card.status === "failed") return null;
  const profit = card.metrics.find((m) => m.key === "pat") ?? card.metrics.find((m) => m.key === "pat_owners");
  const revenue = card.metrics.find((m) => m.key === "revenue");
  for (const [name, metric] of [["Profit", profit], ["Revenue", revenue]] as const) {
    if (!metric) continue;
    if (metric.yoy_swing === "turned loss") return `${name} turned to a loss`;
    if (metric.yoy_swing === "turned profit") return `${name} turned positive`;
    if (metric.yoy_pct === null) continue;
    if (Math.abs(metric.yoy_pct) < 1) return `${name} flat vs last year`;
    return `${name} ${metric.yoy_pct > 0 ? "rose" : "fell"} vs last year`;
  }
  return null;
}

/** Category sentences that run past eight words, said shorter. Used only when no filing-specific note is there. */
const SHORTER: Record<string, string> = {
  litigation: "Legal action can move a stock fast",
};

function words(text: string): string[] {
  return text.split(/\s+/).filter(Boolean);
}

/**
 * The one-line reason on a collapsed card: about eight words, plain. The pipeline's `why` is longer and stays in the details.
 *   results with figures     -> "Profit fell vs last year"
 *   a filing-specific note   -> the note, "Order win" (the pipeline writes it as "<note>. <what the category means>")
 *   otherwise                -> what the category means, "Changes what the company is"
 * Anything still over eight words is cut at a clause, then at eight words.
 */
export function shortWhy(item: Pick<Item, "why" | "category" | "card">): string {
  const fromFigures = resultsWhy(item.card);
  if (fromFigures) return fromFigures;

  let text = item.why.replace(/^Routine:\s*/i, "").trim();
  const sentence = text.indexOf(". ");
  const hasNote = sentence > 0;
  if (hasNote) text = text.slice(0, sentence);
  text = text.replace(/\.$/, "");
  const colon = text.indexOf(": ");
  if (colon > 0) text = text.slice(0, colon); // "A key person is leaving: exits rank above hires"
  const clause = text.search(/,\s+so\b/i);
  if (clause > 0) text = text.slice(0, clause); // "Could not be classified, so it is shown rather than hidden"

  if (words(text).length > MAX_WORDS) text = (!hasNote && SHORTER[item.category]) || `${words(text).slice(0, MAX_WORDS).join(" ")}…`;
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}
