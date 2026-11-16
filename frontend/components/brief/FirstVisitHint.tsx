"use client";

import { useSyncExternalStore } from "react";

const KEY = "finn.hint.brief.v1";
const listeners = new Set<() => void>();

function seen(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false; // blocked storage: the hint shows each visit, which is harmless
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

function dismiss(): void {
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    // not kept: it will show again next visit
  }
  listeners.forEach((listener) => listener());
}

/**
 * One line for a first visit, "Tap any card for numbers and sources", with a way to dismiss it for good (kept in this browser).
 * It is not shown on the server or on first paint, so a returning reader never sees it flash.
 */
export function FirstVisitHint() {
  const dismissed = useSyncExternalStore(subscribe, seen, () => true);
  if (dismissed) return null;
  return (
    <div role="note" data-testid="first-visit-hint" className="mt-3 flex items-center gap-2 rounded-2xl border border-line bg-surface py-0.5 pl-3.5 pr-1">
      <p className="min-w-0 flex-1 text-sm leading-5 text-ink-soft">Tap any card for numbers and sources.</p>
      <button type="button" onClick={dismiss} className="inline-flex min-h-11 shrink-0 items-center rounded-full px-3 text-sm font-semibold text-accent">
        Got it
      </button>
    </div>
  );
}
