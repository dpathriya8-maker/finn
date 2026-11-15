"use client";

import { useState } from "react";
import { DataAsOf } from "@/components/DataAsOf";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { SlidersIcon } from "@/components/ui/Icons";
import { highlightsTitle, windowLabel, WINDOWS } from "@/lib/brief";
import { updateSettings, useSettings } from "@/lib/settings";
import type { AppConfig } from "@/lib/types";
import { useJson } from "@/lib/useJson";

/** The Brief's heading and its one control: a sliders button that opens the time window in a bottom sheet (the thumb zone). */
export function BriefHeader() {
  const configState = useJson<AppConfig>("/data/config.json");
  const settings = useSettings(configState.kind === "ready" ? configState.data : null);
  const [open, setOpen] = useState(false);
  const hours = settings.windowHours;

  return (
    <section aria-labelledby="brief-title" className="pt-4">
      <p className="text-xs font-medium text-ink-faint">Morning Brief</p>
      <div className="flex items-start justify-between gap-3">
        <h1 id="brief-title" className="text-2xl font-semibold tracking-tight">
          {highlightsTitle(hours)}
        </h1>
        <button
          type="button"
          aria-label="Change the time window"
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
          className="-mr-1 inline-flex size-11 shrink-0 items-center justify-center rounded-full border border-line text-ink-soft"
        >
          <SlidersIcon size={20} />
        </button>
      </div>
      <p className="mt-0.5 text-sm text-ink-faint">Showing the last {windowLabel(hours)}</p>
      <div className="mt-1 text-sm text-ink-soft">
        <DataAsOf />
      </div>

      <BottomSheet open={open} onClose={() => setOpen(false)} title="Time window">
        <div role="radiogroup" aria-label="Time window" className="space-y-2">
          {[
            { hours: 24, text: "Last 24 hours" },
            { hours: 72, text: "Last 3 days" },
            { hours: 168, text: "Last 7 days" },
          ].map((option) => {
            const selected = option.hours === hours && WINDOWS.some((w) => w.hours === option.hours);
            return (
              <button
                key={option.hours}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => {
                  updateSettings({ windowHours: option.hours });
                  setOpen(false);
                }}
                className={`flex min-h-12 w-full items-center justify-between rounded-2xl border px-4 text-left text-sm font-medium ${selected ? "border-ink bg-backdrop" : "border-line"}`}
              >
                {option.text}
                {selected && <span aria-hidden="true">✓</span>}
              </button>
            );
          })}
        </div>
        <p className="mt-3 text-xs leading-5 text-ink-faint">The same choice is in Settings.</p>
      </BottomSheet>
    </section>
  );
}
