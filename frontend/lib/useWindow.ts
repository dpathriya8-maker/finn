"use client";

import { effectiveWindow } from "@/lib/brief";
import { isStale, useNowMs } from "@/lib/freshness";
import { useSettings, type Settings } from "@/lib/settings";
import type { AppConfig, Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";

export type WindowState = {
  /** The window actually shown: the reader's choice, or (only for the Brief, only while they have not chosen) the next one that has something material. */
  hours: number;
  /** True when `hours` is wider than the default because the default held nothing material. */
  widened: boolean;
  /** More than 24 hours between when the data was made and the device's clock. */
  stale: boolean;
  generatedAt: string | null;
  settings: Settings;
};

/**
 * The time window of a screen, worked out once for the heading and the content, always counted back from the data's own time
 * (never the device's clock; the clock is used only to say the data is stale). `widen` is for the Brief.
 */
export function useWindow(widen: boolean): WindowState {
  const briefState = useJson<Brief>("/data/brief.json");
  const configState = useJson<AppConfig>("/data/config.json");
  const settings = useSettings(configState.kind === "ready" ? configState.data : null);
  const now = useNowMs();
  const brief = briefState.kind === "ready" ? briefState.data : null;
  const win = brief && widen ? effectiveWindow(brief, settings.windowHours, settings.windowChosen, settings.mutedSymbols) : { hours: settings.windowHours, widened: false };
  return { ...win, stale: brief !== null && now !== null && isStale(brief.generated_at, now), generatedAt: brief?.generated_at ?? null, settings };
}
