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
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max - 1).replace(/\s+\S*$/, "").replace(/[ ,;:\-–]+$/, "");
  return `${cut || clean.slice(0, max - 1)}…`;
}

function pct(value: number | null): string | null {
  if (value === null || !Number.isFinite(value)) return null;
  return `${value >= 0 ? "▲" : "▼"} ${Math.abs(value).toFixed(1)}%`;
}

/**
 * The card's headline: the company's short name first, then the fact, about 70 characters. A results card says
 * what changed from the figures read from the filing; every other card uses the exchange's own subject, tidied by
 * the pipeline. Built by rules; no model.
 */
export function cardHeadline(item: Pick<Item, "company" | "headline" | "card">): string {
  const name = shortName(item.company);
  const card = item.card;
  if (card && card.type === "results" && card.status !== "failed") {
    const revenue = card.metrics.find((m) => m.key === "revenue");
    const profit = card.metrics.find((m) => m.key === "pat") ?? card.metrics.find((m) => m.key === "pat_owners");
    const parts = [
      pct(revenue?.yoy_pct ?? null) && `revenue ${pct(revenue?.yoy_pct ?? null)}`,
      profit?.yoy_swing ? `profit ${profit.yoy_swing}` : pct(profit?.yoy_pct ?? null) && `profit ${pct(profit?.yoy_pct ?? null)}`,
    ].filter(Boolean);
    if (parts.length > 0) return clip(`${name} ${card.period.label}: ${parts.join(", ")} YoY`, MAX);
  }
  const fact = item.headline.replace(new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[:\\-–]?\\s*`, "i"), "");
  return clip(`${name}: ${fact}`, MAX);
}
