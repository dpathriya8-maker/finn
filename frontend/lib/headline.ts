import type { Item } from "@/lib/types";

const MAX = 70;
const SUFFIX = /\s*(?:\(india\)|\bltd\.?|\blimited|\bpvt\.?|\bprivate|\bcorporation|\bcorp\.?)\s*$/i;

/** "Reliance Industries Ltd" -> "Reliance Industries"; "Info Edge (India) Ltd" -> "Info Edge". */
export function shortName(company: string): string {
  let name = company.trim();
  for (let i = 0; i < 4; i++) {
    const next = name.replace(SUFFIX, "").trim();
    if (next === name) break;
    name = next;
  }
  return name || company.trim();
}

/** Two letters for an avatar: the first letters of the first two words of the short name. */
export function initials(company: string): string {
  const words = shortName(company).split(/[\s&-]+/).filter((w) => /[A-Za-z0-9]/.test(w));
  const letters = words.length >= 2 ? words[0][0] + words[1][0] : (words[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}

/** A calm, deterministic hue (0-359) from the symbol, so a company keeps its colour everywhere. */
export function hueFor(symbol: string): number {
  let h = 0;
  for (const ch of symbol) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

function clip(text: string, max: number): string {
  // Collapse ordinary whitespace only: a no-break space (arrow and number in "▼ 3.1%") must survive, and must not be a place to cut.
  const clean = text.replace(/[ \t\r\n\f\v]+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max - 1).replace(/ +[^ ]*$/, "").replace(/[ ,;:\-–]+$/, "");
  return `${cut || clean.slice(0, max - 1)}…`;
}

function pct(value: number | null): string | null {
  if (value === null || !Number.isFinite(value)) return null;
  return `${value >= 0 ? "▲" : "▼"}\u00a0${Math.abs(value).toFixed(1)}%`; // a no-break space keeps the arrow with its number
}

/** What changed, from the figures read in a results filing: "Q2 FY27: revenue ▲ 12.3%, profit ▼ 3.1% YoY". Null for anything else. */
function resultsFact(card: Item["card"]): string | null {
  if (!card || card.type !== "results" || card.status === "failed") return null;
  const revenue = card.metrics.find((m) => m.key === "revenue");
  const profit = card.metrics.find((m) => m.key === "pat") ?? card.metrics.find((m) => m.key === "pat_owners");
  const parts = [
    pct(revenue?.yoy_pct ?? null) && `revenue ${pct(revenue?.yoy_pct ?? null)}`,
    profit?.yoy_swing ? `profit ${profit.yoy_swing}` : pct(profit?.yoy_pct ?? null) && `profit ${pct(profit?.yoy_pct ?? null)}`,
  ].filter(Boolean);
  return parts.length > 0 ? `${card.period.label}: ${parts.join(", ")} YoY` : null;
}

/** The exchange's own subject, tidied by the pipeline, without the company's name if it starts with it. */
function plainFact(item: Pick<Item, "company" | "headline">): string {
  const name = shortName(item.company);
  return item.headline.replace(new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[:\\-–]?\\s*`, "i"), "");
}

/**
 * The card's headline: the company's short name first, then the fact, about 70 characters. A results card says
 * what changed from the figures read from the filing; every other card uses the exchange's own subject, tidied by
 * the pipeline. Built by rules; no model.
 */
export function cardHeadline(item: Pick<Item, "company" | "headline" | "card">): string {
  const name = shortName(item.company);
  const results = resultsFact(item.card);
  if (results) return clip(`${name} ${results}`, MAX);
  return clip(`${name}: ${plainFact(item)}`, MAX);
}

const LINE_MAX = 84;

/**
 * The same fact for a card that already sits under its company's header, so the name is not repeated:
 * "Q2 FY27: revenue ▲ 12.3%, profit ▼ 3.1% YoY" or "Re-appointment of Mr. Rao as Whole-time Director".
 * Short enough for two lines on a phone.
 */
export function filingHeadline(item: Pick<Item, "company" | "headline" | "card">): string {
  const text = resultsFact(item.card) ?? (plainFact(item) || item.headline);
  return clip(text, LINE_MAX);
}
