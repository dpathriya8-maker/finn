"use client";

import { formatPrice } from "@/lib/format";
import { closeCaption, moveLook, priceView, sparkPoints, trendLabel, type PriceView } from "@/lib/prices";
import { hueFor, initials } from "@/lib/headline";
import type { Session } from "@/lib/types";

const MOVE_CLASS = { good: "text-good", bad: "text-bad", flat: "text-ink-faint" } as const;

/** A tiny close-price line, green if the stored period ended higher than it began, red if lower. */
export function Sparkline({ view, width = 64, height = 20 }: { view: PriceView; width?: number; height?: number }) {
  const points = sparkPoints(view.closes, width, height);
  if (!points || view.trendPct === null) return null;
  const up = view.trendPct >= 0;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={trendLabel(view)}
      className={`shrink-0 ${up ? "text-good" : "text-bad"}`}
    >
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** "₹1,339.70  ▼ 1.02%" with the day of that close, from the latest complete session. No data, nothing shown. */
export function PriceChip({ sessions, generatedAt, spark = true }: { sessions?: readonly Session[] | null; generatedAt?: string; spark?: boolean }) {
  const view = priceView(sessions, generatedAt);
  if (!view) return null;
  const move = moveLook(view.changePct);
  return (
    <span className="relative flex shrink-0 items-center gap-2.5">
      {spark && <Sparkline view={view} />}
      <span className="block text-right leading-tight tabular-nums">
        <span className="block text-sm font-semibold text-ink">{formatPrice(view.close)}</span>
        <span className={`block text-xs font-medium ${MOVE_CLASS[move.tone]}`}>
          <span className="sr-only">{move.tone === "good" ? "up " : move.tone === "bad" ? "down " : "flat "}</span>
          {move.text}
        </span>
        <span className="block text-[11px] text-ink-faint">{closeCaption(view.day)}</span>
      </span>
    </span>
  );
}

/**
 * "₹3,430.00 ▼ 1.55%" on one line, the whole chip never wider than it needs and never shrunk or wrapped, so a long company
 * name gives way to it and not the other way round. The move is red, green or grey and also written in words for a screen
 * reader. No sparkline and no date: those are one tap away. `relative` keeps the screen-reader text inside the chip.
 */
export function PriceLine({ sessions, generatedAt }: { sessions?: readonly Session[] | null; generatedAt?: string }) {
  const view = priceView(sessions, generatedAt);
  if (!view) return null;
  const move = moveLook(view.changePct);
  return (
    <span className="relative flex shrink-0 items-baseline gap-1.5 whitespace-nowrap rounded-full bg-backdrop px-2.5 py-1 tabular-nums">
      <span className="text-sm font-semibold text-ink">{formatPrice(view.close)}</span>
      <span className={`text-xs font-medium ${MOVE_CLASS[move.tone]}`}>
        <span className="sr-only">{move.tone === "good" ? "up " : move.tone === "bad" ? "down " : "flat "}</span>
        {move.text}
      </span>
    </span>
  );
}

/** The 30-day line and the day of the close it ends on: the price detail behind a tap. */
export function PriceTrend({ sessions, generatedAt }: { sessions?: readonly Session[] | null; generatedAt?: string }) {
  const view = priceView(sessions, generatedAt);
  if (!view) return null;
  return (
    <span className="flex items-center gap-2 text-xs text-ink-faint">
      <Sparkline view={view} />
      <span>
        {view.closes.length}-day trend · {closeCaption(view.day)}
      </span>
    </span>
  );
}

/** A round badge with the company's initials in a calm colour that is the same everywhere for that symbol. */
export function Avatar({ symbol, name, size = 36 }: { symbol: string; name: string; size?: number }) {
  return (
    <span
      className="avatar inline-flex shrink-0 items-center justify-center rounded-full text-xs font-semibold"
      style={{ width: size, height: size, ["--h" as string]: hueFor(symbol) }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
