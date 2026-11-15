import { useMemo, useSyncExternalStore } from "react";
import type { PriceView } from "@/lib/prices";

/**
 * "My money", without an account: how much the reader has put into each company, and optionally the average price they paid.
 * Kept in this browser's localStorage and nowhere else. Every rupee figure in the app that is about the reader's own money is
 * worked out here, in code, from real closes (the What-if calculator shares `formatInr` and `dayChange`); nothing is estimated
 * where a number is missing: no buy price means no profit or loss, only the day's change.
 */
const KEY = "finn.holdings.v2";
const LEGACY_KEY = "finn.invested.v1"; // amounts only, from before buy prices; still read, never written
const MAX_AMOUNT = 1_000_000_000_000; // ₹1 lakh crore: far more than anyone types, and still exact in a number
const MIN_PRICE = 0.01;
const MAX_PRICE = 10_000_000; // ₹1 crore a share
const SYMBOL = /^[A-Z0-9&-]{1,20}$/;
const listeners = new Set<() => void>();

/** One company: what was put in, what was paid per share (optional), and whether these numbers are the SAMPLE ones. */
export type Holding = { amount?: number; buyPrice?: number; sample?: boolean };
export type Holdings = Record<string, Holding>;
/** Kept for the screens that only need the amounts. */
export type Invested = Holdings;

// ---------------------------------------------------------------------------------------------------------- typing in a box
export type ParsedInput = { value: number | null; valid: boolean };

function parseNumber(text: string, min: number, max: number): ParsedInput {
  const clean = text.replace(/[₹,\s]/g, "");
  if (clean === "") return { value: null, valid: true };
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return { value: null, valid: false };
  const value = Number(clean);
  return value >= min && value <= max ? { value, valid: true } : { value: null, valid: false };
}

/** What was typed in the amount box: "" is "not set", "1,50,000" and "₹50000" are read, anything else is invalid. */
export function parseAmountInput(text: string): ParsedInput {
  return parseNumber(text, 0, MAX_AMOUNT);
}

/** What was typed in the buy price box: the same, but a price must be at least 1 paisa. */
export function parsePriceInput(text: string): ParsedInput {
  return parseNumber(text, MIN_PRICE, MAX_PRICE);
}

/** "1,50,000" or "1,234.5": Indian digit grouping, no symbol, for a box that is not being edited. */
export function formatInputNumber(value: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

// ---------------------------------------------------------------------------------------------------------------- storage
function validAmount(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 && value <= MAX_AMOUNT;
}

function validPrice(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= MIN_PRICE && value <= MAX_PRICE;
}

/** Anything unexpected in storage is ignored, never trusted. A bare number is the old amounts-only format. */
export function parseHoldings(raw: string): Holdings {
  try {
    const data: unknown = JSON.parse(raw);
    if (typeof data !== "object" || data === null || Array.isArray(data)) return {};
    const out: Holdings = {};
    for (const [symbol, value] of Object.entries(data)) {
      if (!SYMBOL.test(symbol)) continue;
      if (typeof value === "number") {
        if (validAmount(value)) out[symbol] = { amount: value };
      } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
        const v = value as Record<string, unknown>;
        const holding: Holding = {};
        if (validAmount(v.amount)) holding.amount = v.amount;
        if (validPrice(v.buyPrice)) holding.buyPrice = v.buyPrice;
        if (v.sample === true && Object.keys(holding).length > 0) holding.sample = true;
        if (Object.keys(holding).length > 0) out[symbol] = holding;
      }
    }
    return out;
  } catch {
    return {};
  }
}

/** The amounts only, by symbol (the shape the first version stored). */
export function parseInvested(raw: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [symbol, holding] of Object.entries(parseHoldings(raw))) if (holding.amount !== undefined) out[symbol] = holding.amount;
  return out;
}

function readRaw(): string {
  try {
    return window.localStorage.getItem(KEY) ?? window.localStorage.getItem(LEGACY_KEY) ?? "{}";
  } catch {
    return "{}"; // private mode or blocked storage: nothing is kept, and nothing breaks
  }
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", callback);
  };
}

function save(next: Holdings): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage unavailable: the entry is not kept
  }
  listeners.forEach((listener) => listener());
}

/**
 * Change one company's entry: a number sets that field, null clears it, undefined leaves it alone. An entry with nothing left in it
 * is removed. Editing an entry makes it the reader's own, so the SAMPLE tag comes off that company.
 */
export function setHolding(symbol: string, change: { amount?: number | null; buyPrice?: number | null }): void {
  const next = parseHoldings(readRaw());
  const holding: Holding = { ...next[symbol] };
  if (holding.sample) {
    // A sample entry is made up, so the part the reader did not type goes too: their number is never mixed with an invented one.
    if (change.amount !== undefined) delete holding.buyPrice;
    if (change.buyPrice !== undefined) delete holding.amount;
  }
  delete holding.sample;
  if (change.amount !== undefined) {
    if (change.amount === null || !validAmount(change.amount)) delete holding.amount;
    else holding.amount = change.amount;
  }
  if (change.buyPrice !== undefined) {
    if (change.buyPrice === null || !validPrice(change.buyPrice)) delete holding.buyPrice;
    else holding.buyPrice = change.buyPrice;
  }
  if (Object.keys(holding).length === 0) delete next[symbol];
  else next[symbol] = holding;
  save(next);
}

/** Back-compatible: save one company's amount (null or 0 clears it). */
export function setInvested(symbol: string, amount: number | null): void {
  setHolding(symbol, { amount });
}

/** Replace everything with the SAMPLE entries given. The caller asks first when the reader has entries of their own. */
export function applySample(entries: Holdings): void {
  const next: Holdings = {};
  for (const [symbol, holding] of Object.entries(parseHoldings(JSON.stringify(entries)))) next[symbol] = { ...holding, sample: true };
  save(next);
}

/** Remove only the SAMPLE entries; whatever the reader typed stays. */
export function clearSample(): void {
  const next = parseHoldings(readRaw());
  for (const symbol of Object.keys(next)) if (next[symbol].sample) delete next[symbol];
  save(next);
}

export function hasSample(holdings: Holdings): boolean {
  return Object.values(holdings).some((h) => h.sample && h.amount !== undefined);
}

/** True when the reader has typed something of their own (what a sample would overwrite). */
export function hasOwnEntries(holdings: Holdings): boolean {
  return Object.values(holdings).some((h) => !h.sample);
}

/** The saved holdings by symbol. Empty on the server and on first paint, so the page hydrates cleanly. */
export function useInvested(): Holdings {
  const raw = useSyncExternalStore(subscribe, readRaw, () => "{}");
  return useMemo(() => parseHoldings(raw), [raw]);
}

// ---------------------------------------------------------------------------------------------------------------- showing money
/** "₹1,50,000": Indian digit grouping, whole rupees. */
export function formatInr(amount: number): string {
  return "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Math.round(amount));
}

export type Direction = "good" | "bad" | "flat";

export function directionOf(rupees: number): Direction {
  const whole = Math.round(rupees);
  return whole > 0 ? "good" : whole < 0 ? "bad" : "flat";
}

/** "▲ ₹4,200", "▼ ₹775" or "₹0": whole rupees, the arrow is part of the number so colour is never the only signal. */
export function arrowInr(rupees: number): string {
  const whole = Math.round(Math.abs(rupees)); // half a rupee rounds away from zero, the same for a gain and a loss
  if (whole === 0) return formatInr(0);
  return `${rupees > 0 ? "▲" : "▼"} ${formatInr(whole)}`;
}

/** "8.4%" with the sign left to the arrow beside it; two decimals when a move is so small that one would show 0.0%. */
export function plainPct(pct: number): string {
  const abs = Math.abs(pct);
  return `${(abs > 0 && abs < 0.1 ? abs.toFixed(2) : abs.toFixed(1))}%`;
}

/** "▲ ₹4,200 (8.4%)". */
export function arrowInrPct(rupees: number, pct: number): string {
  return `${arrowInr(rupees)}${Math.round(Math.abs(rupees)) === 0 ? "" : ` (${plainPct(pct)})`}`;
}

export function totalInvested(holdings: Holdings, symbols: readonly string[]): number {
  return symbols.reduce((sum, symbol) => sum + (holdings[symbol]?.amount ?? 0), 0);
}

/** What a day's move did to an amount, in rupees: amount × change%. */
export function dayChange(amount: number, changePct: number): number {
  return (amount * changePct) / 100;
}

// ----------------------------------------------------------------------------------------------------- one company's position
/** The latest complete close of a company and the one before it: all a position needs from the price data. */
export type Quote = { close: number; prevClose: number | null; changePct: number };

export function quoteOf(view: Pick<PriceView, "close" | "prevClose" | "changePct"> | null): Quote | null {
  return view ? { close: view.close, prevClose: view.prevClose, changePct: view.changePct } : null;
}

export type Position = {
  symbol: string;
  amount: number;
  buyPrice: number | null;
  sample: boolean;
  /** Shares held, from amount ÷ buy price; null without a buy price. */
  shares: number | null;
  /** What it is worth at the latest close; null without a buy price (or a price). */
  value: number | null;
  /** value − amount, in rupees and in percent of the amount. Null without a buy price (or a price): no fake profit or loss. */
  pnl: number | null;
  pnlPct: number | null;
  /** Today's move in rupees: shares × (close − previous close) with a buy price, else amount × the day's change; null with no price. */
  today: number | null;
};

/** A position from a holding and the latest quote. Null when there is no amount. */
export function position(symbol: string, holding: Holding | undefined, quote: Quote | null): Position | null {
  const amount = holding?.amount;
  if (!holding || amount === undefined || !validAmount(amount)) return null;
  const buyPrice = validPrice(holding.buyPrice) ? holding.buyPrice : null;
  const base = { symbol, amount, buyPrice, sample: holding.sample === true };
  if (!quote || !Number.isFinite(quote.close) || quote.close <= 0) return { ...base, shares: null, value: null, pnl: null, pnlPct: null, today: null };
  if (buyPrice === null) return { ...base, shares: null, value: null, pnl: null, pnlPct: null, today: dayChange(amount, quote.changePct) };
  const shares = amount / buyPrice;
  const value = shares * quote.close;
  const pnl = value - amount;
  const today = quote.prevClose !== null && Number.isFinite(quote.prevClose) && quote.prevClose > 0 ? shares * (quote.close - quote.prevClose) : dayChange(value, quote.changePct);
  return { ...base, shares, value, pnl, pnlPct: (pnl / amount) * 100, today };
}

/** "Your ₹50,000 · ▼ ₹775 today · ▲ ₹4,200 overall": overall only when there is a buy price. */
export type HoldingPart = { text: string; tone: Direction };
export type HoldingLine = { lead: string; parts: HoldingPart[]; sample: boolean };

export function holdingLine(p: Position): HoldingLine {
  const parts: HoldingPart[] = [];
  if (p.today !== null) {
    const tone = directionOf(p.today);
    parts.push({ text: tone === "flat" ? "unchanged today" : `${arrowInr(p.today)} today`, tone });
  }
  if (p.pnl !== null) {
    const tone = directionOf(p.pnl);
    parts.push({ text: tone === "flat" ? "even overall" : `${arrowInr(p.pnl)} overall`, tone });
  }
  return { lead: `Your ${formatInr(p.amount)}`, parts, sample: p.sample };
}

// --------------------------------------------------------------------------------------------------------- the whole portfolio
export type Summary = {
  /** Holdings with an amount. */
  count: number;
  /** Of those, how many have a buy price and a price (so a value and a profit or loss). */
  priced: number;
  /** Of those, how many are SAMPLE. */
  sampleCount: number;
  invested: number;
  /** Over the priced holdings only; null when there are none. */
  pricedInvested: number;
  value: number | null;
  overall: number | null;
  overallPct: number | null;
  /** Over every holding that has a price. */
  today: number | null;
  /** What the weights are shares of: current value when every holding has one, else the amount invested. */
  weightBasis: "value" | "invested";
  /** Biggest loss first: priced holdings by profit or loss, lowest first, then the rest by today's move. */
  rows: (Position & { weight: number })[];
};

export function summarize(holdings: Holdings, symbols: readonly string[], quoteOf: (symbol: string) => Quote | null): Summary | null {
  const all = symbols.map((symbol) => position(symbol, holdings[symbol], quoteOf(symbol))).filter((p): p is Position => p !== null);
  if (all.length === 0) return null;
  const priced = all.filter((p) => p.pnl !== null);
  const invested = all.reduce((sum, p) => sum + p.amount, 0);
  const pricedInvested = priced.reduce((sum, p) => sum + p.amount, 0);
  const value = priced.length > 0 ? priced.reduce((sum, p) => sum + (p.value ?? 0), 0) : null;
  const overall = value === null ? null : value - pricedInvested;
  const withToday = all.filter((p) => p.today !== null);
  const today = withToday.length > 0 ? withToday.reduce((sum, p) => sum + (p.today ?? 0), 0) : null;
  const weightBasis = priced.length === all.length ? "value" : "invested";
  const weightOf = (p: Position) => (weightBasis === "value" ? (p.value ?? 0) : p.amount);
  const total = all.reduce((sum, p) => sum + weightOf(p), 0);
  const rows = all
    .map((p) => ({ ...p, weight: total > 0 ? (weightOf(p) / total) * 100 : 0 }))
    .sort((a, b) => {
      if ((a.pnl === null) !== (b.pnl === null)) return a.pnl === null ? 1 : -1; // priced first
      if (a.pnl !== null && b.pnl !== null) return a.pnl - b.pnl || a.symbol.localeCompare(b.symbol);
      return (a.today ?? 0) - (b.today ?? 0) || a.symbol.localeCompare(b.symbol);
    });
  return {
    count: all.length,
    priced: priced.length,
    sampleCount: all.filter((p) => p.sample).length,
    invested,
    pricedInvested,
    value,
    overall,
    overallPct: overall === null || pricedInvested === 0 ? null : (overall / pricedInvested) * 100,
    today,
    weightBasis,
    rows,
  };
}

// ------------------------------------------------------------------------------------------------------------ sample holdings
const SAMPLE_AMOUNTS = [50_000, 25_000, 100_000, 15_000, 75_000, 40_000];
// What each sample company's buy price is, as a share of its latest close: a mix of gains and losses, so the screens show both.
const SAMPLE_COST_FACTORS = [0.86, 1.12, 0.95, 1.3, 1.04, 0.78];

/**
 * Made-up holdings so the screens can be tried without typing: the first six portfolio companies (in the order given) that have a
 * price, each with a fixed amount, and a buy price set to a fixed share of its latest close. They are SAMPLE, and are labelled so
 * everywhere they appear. Nothing here pretends to be the reader's money.
 */
export function sampleHoldings(companies: readonly { symbol: string; close: number | null }[]): Holdings {
  const out: Holdings = {};
  let i = 0;
  for (const c of companies) {
    if (i >= SAMPLE_AMOUNTS.length) break;
    if (c.close === null || !Number.isFinite(c.close) || c.close <= 0) continue;
    out[c.symbol] = { amount: SAMPLE_AMOUNTS[i], buyPrice: Math.round(c.close * SAMPLE_COST_FACTORS[i] * 100) / 100, sample: true };
    i += 1;
  }
  return out;
}
