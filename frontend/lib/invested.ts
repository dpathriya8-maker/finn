import { useMemo, useSyncExternalStore } from "react";

/**
 * "My money", without an account: how much the reader has put into each company, kept in this browser's localStorage and nowhere
 * else. It is used to show what a day's move means in rupees (amount × the real day change, computed here), and for nothing else.
 */
const KEY = "finn.invested.v1";
const MAX_AMOUNT = 1_000_000_000_000; // ₹1 lakh crore: far more than anyone types, and still exact in a number
const listeners = new Set<() => void>();

export type Invested = Record<string, number>;

/** What was typed in the amount box: "" is "not set", "1,50,000" and "₹50000" are read, anything else is invalid. */
export function parseAmountInput(text: string): { value: number | null; valid: boolean } {
  const clean = text.replace(/[₹,\s]/g, "");
  if (clean === "") return { value: null, valid: true };
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return { value: null, valid: false };
  const value = Number(clean);
  return value >= 0 && value <= MAX_AMOUNT ? { value, valid: true } : { value: null, valid: false };
}

/** Anything unexpected in storage is ignored, never trusted. */
export function parseInvested(raw: string): Invested {
  try {
    const data: unknown = JSON.parse(raw);
    if (typeof data !== "object" || data === null || Array.isArray(data)) return {};
    const out: Invested = {};
    for (const [symbol, value] of Object.entries(data)) {
      if (/^[A-Z0-9&-]{1,20}$/.test(symbol) && typeof value === "number" && Number.isFinite(value) && value > 0 && value <= MAX_AMOUNT) out[symbol] = value;
    }
    return out;
  } catch {
    return {};
  }
}

/** "₹1,50,000": Indian digit grouping, whole rupees. */
export function formatInr(amount: number): string {
  return "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Math.round(amount));
}

export function totalInvested(invested: Invested, symbols: readonly string[]): number {
  return symbols.reduce((sum, symbol) => sum + (invested[symbol] ?? 0), 0);
}

/** What a day's move did to an amount, in rupees: amount × change%. */
export function dayChange(amount: number, changePct: number): number {
  return (amount * changePct) / 100;
}

export type HoldingLine = { lead: string; move: string; tone: "good" | "bad" | "flat" };

/** "Your ₹50,000 · ▼ ₹775 today": the lead in grey, the move in red or green with its arrow. A move under ₹1 is "unchanged". */
export function holdingLine(amount: number, changePct: number): HoldingLine {
  const change = Math.round(dayChange(amount, changePct));
  const lead = `Your ${formatInr(amount)} · `;
  if (change === 0) return { lead, move: "unchanged today", tone: "flat" };
  return { lead, move: `${change > 0 ? "▲" : "▼"} ${formatInr(Math.abs(change))} today`, tone: change > 0 ? "good" : "bad" };
}

function readRaw(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "{}";
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

/** Save one company's amount (null or 0 clears it) and tell every screen that shows it. */
export function setInvested(symbol: string, amount: number | null): void {
  const next = parseInvested(readRaw());
  if (amount === null || amount <= 0) delete next[symbol];
  else next[symbol] = amount;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage unavailable: the amount is not kept
  }
  listeners.forEach((listener) => listener());
}

/** The saved amounts by symbol. Empty on the server and on first paint, so the page hydrates cleanly. */
export function useInvested(): Invested {
  const raw = useSyncExternalStore(subscribe, readRaw, () => "{}");
  return useMemo(() => parseInvested(raw), [raw]);
}
