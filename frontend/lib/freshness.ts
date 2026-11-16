import { useSyncExternalStore } from "react";

/** Data is called stale when it is more than a day older than the device's clock. */
export const STALE_AFTER_MS = 24 * 3_600_000;

/** Whether data made at `generatedAt` is more than 24 hours older than `nowMs`. Anything that is not a date is not called stale. */
export function isStale(generatedAt: string | null | undefined, nowMs: number): boolean {
  if (!generatedAt) return false;
  const at = Date.parse(generatedAt);
  return Number.isFinite(at) && nowMs - at > STALE_AFTER_MS;
}

function subscribe(callback: () => void): () => void {
  const timer = window.setInterval(callback, 60_000);
  return () => window.clearInterval(timer);
}

/**
 * The device's clock to the minute, or null on the server and on first paint (the server cannot know the reader's clock), then it
 * fills in and moves on by itself. Used for one thing only: telling whether the data is stale. Windows are never counted from it.
 */
export function useNowMs(): number | null {
  const minute = useSyncExternalStore(
    subscribe,
    () => Math.floor(Date.now() / 60_000),
    () => null,
  );
  return minute === null ? null : minute * 60_000;
}
