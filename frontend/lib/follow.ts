"use client";

import { useMemo, useSyncExternalStore } from "react";
import { plainName } from "@/lib/people";

/**
 * What the reader follows: company symbols, people (by full name) and topics (by id). Kept in this browser only (localStorage), like
 * the settings: no accounts, nothing sent anywhere. Following picks which filings appear in the Following feed on the Interested tab
 * (see lib/followMatch.ts); it does not send push notifications.
 */
export type Follow = { companies: string[]; people: string[]; topics: string[] };

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

/** The first version stored a person as "SYMBOL:Mr. Name"; a person is now followed by their name alone, without honorific. */
function personName(stored: string): string {
  return plainName(stored.replace(/^[A-Z0-9&-]{1,20}:/, ""));
}

/** Anything unexpected in storage is ignored, never trusted. */
export function parseFollow(raw: string): Follow {
  try {
    const data: unknown = JSON.parse(raw);
    if (data && typeof data === "object") {
      const o = data as Record<string, unknown>;
      const people: string[] = [];
      for (const name of strings(o.people).map(personName)) if (!people.some((p) => p.toLowerCase() === name.toLowerCase())) people.push(name);
      return { companies: strings(o.companies), people, topics: strings(o.topics) };
    }
  } catch {
    /* fall through */
  }
  return { companies: [], people: [], topics: [] };
}

/** Add the id, or take it out if it is there (people compare without regard to case). */
export function toggled(list: readonly string[], id: string): string[] {
  const same = (x: string) => x === id || x.toLowerCase() === id.toLowerCase();
  return list.some(same) ? list.filter((x) => !same(x)) : [...list, id].slice(-LIMIT);
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
