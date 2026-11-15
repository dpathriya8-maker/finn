import type { Session } from "@/lib/types";

/** What a price chip and a sparkline need, worked out from the stored sessions. Nothing here is invented: no sessions, no view. */
export type PriceView = {
  close: number;
  changePct: number;
  /** Trading day of the latest complete session, YYYY-MM-DD. */
  day: string;
  closes: number[];
  /** Change from the first stored close to the last, in percent; null with fewer than two sessions. */
  trendPct: number | null;
};

const IST = "Asia/Kolkata";
const MARKET_CLOSED_MINUTES = 15 * 60 + 45; // 3:45 pm IST: the cash market closes at 3:30 pm

function istParts(ms: number): { day: string; minutes: number } {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: IST, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(ms);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return { day: `${get("year")}-${get("month")}-${get("day")}`, minutes: Number(get("hour")) * 60 + Number(get("minute")) };
}

/** Sessions without today's if the data was made while the market was still open (that bar is not a close yet). */
export function completeSessions(sessions: readonly Session[], generatedAt?: string): Session[] {
  const last = sessions[sessions.length - 1];
  if (!last || !generatedAt) return [...sessions];
  const at = Date.parse(generatedAt);
  if (Number.isNaN(at)) return [...sessions];
  const now = istParts(at);
  return last.day === now.day && now.minutes < MARKET_CLOSED_MINUTES ? sessions.slice(0, -1) : [...sessions];
}

export function priceView(sessions: readonly Session[] | undefined | null, generatedAt?: string): PriceView | null {
  if (!sessions || sessions.length === 0) return null;
  const done = completeSessions(sessions, generatedAt);
  const last = done[done.length - 1];
  if (!last || !Number.isFinite(last.close)) return null;
  const closes = done.map((s) => s.close).filter((c) => Number.isFinite(c));
  const first = closes[0];
  const trendPct = closes.length >= 2 && first > 0 ? (last.close / first - 1) * 100 : null;
  return { close: last.close, changePct: last.change_pct, day: last.day, closes, trendPct };
}

export type MoveLook = { text: string; tone: "good" | "bad" | "flat" };

/** "▲ 1.02%", "▼ 1.02%" or "0.00%": green up, red down, grey flat. */
export function moveLook(changePct: number): MoveLook {
  const abs = Math.abs(changePct).toFixed(2);
  if (Number(abs) === 0) return { text: "0.00%", tone: "flat" };
  return changePct > 0 ? { text: `▲ ${abs}%`, tone: "good" } : { text: `▼ ${abs}%`, tone: "bad" };
}

/** "13 Nov close" for a trading day written as YYYY-MM-DD. */
export function closeCaption(day: string): string {
  const date = new Date(`${day}T12:00:00+05:30`);
  if (Number.isNaN(date.getTime())) return "close";
  return `${new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "short" }).format(date)} close`;
}

/** "30-day price trend, up 4.2%" (the number of days is how many sessions are stored). */
export function trendLabel(view: Pick<PriceView, "trendPct" | "closes">): string {
  if (view.trendPct === null) return "Price trend not available";
  const dir = view.trendPct >= 0 ? "up" : "down";
  return `${view.closes.length}-day price trend, ${dir} ${Math.abs(view.trendPct).toFixed(1)}%`;
}

/** The points of a polyline that fits width x height, with the lowest close at the bottom. */
export function sparkPoints(closes: readonly number[], width: number, height: number, pad = 2): string {
  if (closes.length < 2) return "";
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min;
  const step = (width - pad * 2) / (closes.length - 1);
  return closes
    .map((c, i) => {
      const x = pad + i * step;
      const y = span === 0 ? height / 2 : pad + (1 - (c - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}
