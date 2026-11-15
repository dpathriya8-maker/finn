import { formatInr } from "@/lib/invested";
import { completeSessions } from "@/lib/prices";
import type { Session } from "@/lib/types";

/**
 * The maths of the "What if" calculator, all in code and all from real closes: an amount, a move in percent, and what that means in
 * rupees. Nothing here predicts anything; it only restates a percentage in rupees, which is how most people think about their money.
 */
const MINUS = "−"; // a real minus sign, not a hyphen

export const DEFAULT_AMOUNT = 10_000;
export const SLIDER_MIN = -20;
export const SLIDER_MAX = 20;
export const CHIPS = [-10, -5, 5, 10] as const;

export type Tone = "good" | "bad" | "flat";

/** Whole rupees of change for an amount and a move: amount × percent. Anything that is not a finite number is no change. */
export function rupeeChange(amount: number, pct: number): number {
  if (!Number.isFinite(amount) || !Number.isFinite(pct)) return 0;
  const change = Math.round((amount * pct) / 100);
  return change === 0 ? 0 : change; // never "-0"
}

/** "+₹420", "−₹155", "₹0": the sign is always written, with Indian digit grouping. */
export function signedInr(rupees: number): string {
  const whole = Math.round(rupees);
  if (whole === 0) return formatInr(0);
  return `${whole > 0 ? "+" : MINUS}${formatInr(Math.abs(whole))}`;
}

export function toneOf(change: number): Tone {
  return change > 0 ? "good" : change < 0 ? "bad" : "flat";
}

/** "▼1.55%", "▲4.2%", or "0.00%" for a move that rounds to nothing: the arrow is part of the number, so colour is never the only signal. */
export function arrowPct(pct: number, digits = 2): string {
  const abs = Math.abs(pct).toFixed(digits);
  if (Number(abs) === 0) return `${(0).toFixed(digits)}%`;
  return `${pct > 0 ? "▲" : "▼"}${abs}%`;
}

export type WhatIfRow = { label: string; text: string; tone: Tone };

/** One row: "Today (▼1.55%)" and "−₹155", from a real move in percent. */
export function changeRow(label: string, pct: number, amount: number, digits = 2): WhatIfRow {
  const change = rupeeChange(amount, pct);
  return { label: `${label} (${arrowPct(pct, digits)})`, text: signedInr(change), tone: toneOf(change) };
}

/** "−10%", "+5%" or "0%". */
export function signedPct(pct: number): string {
  return pct === 0 ? "0%" : `${pct > 0 ? "+" : MINUS}${Math.abs(pct)}%`;
}

export function scenario(amount: number, pct: number): { change: number; total: number; tone: Tone } {
  const change = rupeeChange(amount, pct);
  return { change, total: (Number.isFinite(amount) ? amount : 0) + change, tone: toneOf(change) };
}

/** The slider's spoken value: "minus 10 percent, you'd have 9,000 rupees". */
export function ariaValueText(amount: number, pct: number): string {
  const { total } = scenario(amount, pct);
  const rupees = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Math.round(total));
  const move = pct === 0 ? "no change" : `${pct > 0 ? "plus" : "minus"} ${Math.abs(pct)} percent`;
  return `${move}, you'd have ${rupees} rupees`;
}

function minusDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - days);
  return date.toISOString().slice(0, 10);
}

/**
 * The real move over the last `days` calendar days: the latest complete close against the last close on or before that many days
 * earlier. Null when the stored history does not reach back that far (the row is then left out, never estimated).
 */
export function periodChange(sessions: readonly Session[] | undefined | null, generatedAt: string | undefined, days = 30): { pct: number; fromDay: string } | null {
  if (!sessions || sessions.length < 2) return null;
  const done = completeSessions(sessions, generatedAt);
  const last = done[done.length - 1];
  if (!last || !Number.isFinite(last.close)) return null;
  const target = minusDays(last.day, days);
  const reference = [...done].reverse().find((s) => s.day <= target && Number.isFinite(s.close) && s.close > 0);
  if (!reference) return null;
  return { pct: (last.close / reference.close - 1) * 100, fromDay: reference.day };
}
