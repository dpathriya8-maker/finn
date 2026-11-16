"use client";

import { whenLabel } from "@/lib/brief";
import { isStale, useNowMs } from "@/lib/freshness";
import { formatIst } from "@/lib/format";

/**
 * The end of a finite feed. With current data: "You're all caught up", checked "Today, 4:55 am". With data more than a day older than
 * the device's clock it does not say "today" or "caught up": "That's everything in the latest data", checked "16 Nov, 4:55 am IST".
 */
export function CaughtUp({ generatedAt, className = "" }: { generatedAt: string; className?: string }) {
  const now = useNowMs();
  const stale = now !== null && isStale(generatedAt, now);
  return (
    <p className={`text-center text-sm text-ink-soft ${className}`} data-testid="caught-up">
      <span className="font-semibold text-good" aria-hidden="true">
        ✓
      </span>{" "}
      {stale ? "That's everything in the latest data" : "You're all caught up"}
      <span className="mt-1 block text-xs text-ink-faint">Checked {stale ? formatIst(generatedAt) : whenLabel(generatedAt, generatedAt)}</span>
    </p>
  );
}
