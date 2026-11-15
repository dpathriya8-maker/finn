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
    <span className="flex shrink-0 items-center gap-2.5">
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
