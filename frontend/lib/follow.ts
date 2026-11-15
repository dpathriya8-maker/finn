"use client";

import { useMemo, useSyncExternalStore } from "react";

/**
 * Who the reader follows: company symbols and people. Kept in this browser only (localStorage), like the settings:
 * no accounts, nothing sent anywhere. This is a PREVIEW of personalisation; following does not yet trigger any alert.
 */
export type Follow = { companies: string[]; people: string[] };

const KEY = "finn.follow.v1";
const EMPTY = "{}";
const LIMIT = 200;
const listeners = new Set<() => void>();

function readRaw(): string {
  try {
    return window.localStorage.getItem(KEY) ?? EMPTY;
  } catch {
    return EMPTY; // private mode or blocked storage: following simply does not persist
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

function strings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((v): v is string => typeof v === "string" && v.length > 0 && v.length <= 120))].slice(0, LIMIT);
}

/** Anything unexpected in storage is ignored, never trusted. */
export function parseFollow(raw: string): Follow {
  try {
    const data: unknown = JSON.parse(raw);
    if (data && typeof data === "object") {
      const o = data as Record<string, unknown>;
      return { companies: strings(o.companies), people: strings(o.people) };
    }
  } catch {
    /* fall through */
  }
  return { companies: [], people: [] };
}

export function toggled(list: readonly string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id].slice(-LIMIT);
}

export function toggleFollow(kind: keyof Follow, id: string): void {
  const current = parseFollow(readRaw());
  const next: Follow = { ...current, [kind]: toggled(current[kind], id) };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: nothing to persist */
  }
  listeners.forEach((listener) => listener());
}

export function useFollow(): Follow {
  const raw = useSyncExternalStore(subscribe, readRaw, () => EMPTY);
  return useMemo(() => parseFollow(raw), [raw]);
}
