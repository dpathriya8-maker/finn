import { useMemo, useSyncExternalStore } from "react";
import type { AppConfig } from "@/lib/types";

/**
 * User settings live in localStorage: no accounts, no personal data. Only what the user changed is
 * stored; everything else follows the defaults the pipeline publishes in config.json, so a change of
 * default reaches everyone who never touched that setting.
 */
export type Overrides = {
  windowHours?: number;
  volumeMultiple?: number;
  priceMovePct?: number;
  mutedSymbols?: string[];
  /** category id -> alert on or off, only where the user differs from the default */
  alertCategories?: Record<string, boolean>;
};

export type Settings = {
  windowHours: number;
  volumeMultiple: number;
  priceMovePct: number;
  mutedSymbols: string[];
  /** category id -> whether it pushes an alert */
  alertCategories: Record<string, boolean>;
};

const KEY = "finn.settings.v1";
const EMPTY = "{}";
const listeners = new Set<() => void>();

// Used until config.json arrives; identical to config/defaults.json.
const FALLBACK = { window_hours: 24, volume_multiple: 2, price_move_pct: 5 };

function readRaw(): string {
  try {
    return window.localStorage.getItem(KEY) ?? EMPTY;
  } catch {
    return EMPTY; // private mode or blocked storage: the app still works on defaults
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

function num(value: unknown, min: number, max: number): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max ? value : undefined;
}

/** Anything unexpected in storage is ignored, never trusted. */
export function parseOverrides(raw: string): Overrides {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return {};
  }
  if (typeof data !== "object" || data === null) return {};
  const o = data as Record<string, unknown>;
  const out: Overrides = {};
  const windowHours = num(o.windowHours, 1, 24 * 30);
  const volumeMultiple = num(o.volumeMultiple, 1, 100);
  const priceMovePct = num(o.priceMovePct, 0.1, 100);
  if (windowHours !== undefined) out.windowHours = windowHours;
  if (volumeMultiple !== undefined) out.volumeMultiple = volumeMultiple;
  if (priceMovePct !== undefined) out.priceMovePct = priceMovePct;
  if (Array.isArray(o.mutedSymbols)) out.mutedSymbols = o.mutedSymbols.filter((s): s is string => typeof s === "string");
  if (typeof o.alertCategories === "object" && o.alertCategories !== null) {
    out.alertCategories = Object.fromEntries(
      Object.entries(o.alertCategories).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean"),
    );
  }
  return out;
}

export function resolveSettings(overrides: Overrides, config: AppConfig | null): Settings {
  const defaults = config?.defaults ?? FALLBACK;
  const alertCategories: Record<string, boolean> = {};
  for (const category of config?.categories ?? []) {
    alertCategories[category.id] = overrides.alertCategories?.[category.id] ?? category.default_alert;
  }
  return {
    windowHours: overrides.windowHours ?? defaults.window_hours,
    volumeMultiple: overrides.volumeMultiple ?? defaults.volume_multiple,
    priceMovePct: overrides.priceMovePct ?? defaults.price_move_pct,
    mutedSymbols: overrides.mutedSymbols ?? [],
    alertCategories,
  };
}

/** Merge a change into storage and tell every component that reads settings. */
export function updateSettings(change: Overrides): void {
  const merged = { ...parseOverrides(readRaw()), ...change };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(merged));
  } catch {
    // storage unavailable: the change is not saved, and the screen simply keeps the old value
  }
  listeners.forEach((listener) => listener());
}

export function useSettings(config: AppConfig | null): Settings {
  const raw = useSyncExternalStore(subscribe, readRaw, () => EMPTY);
  return useMemo(() => resolveSettings(parseOverrides(raw), config), [raw, config]);
}
