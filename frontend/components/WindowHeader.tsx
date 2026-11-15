"use client";

import { useId, useState, type ReactNode } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { SlidersIcon } from "@/components/ui/Icons";
import { highlightsTitle, windowLabel, WINDOWS } from "@/lib/brief";
import { updateSettings, useSettings } from "@/lib/settings";
import type { AppConfig } from "@/lib/types";
import { useJson } from "@/lib/useJson";

const OPTIONS = [
  { hours: 24, text: "Last 24 hours" },
  { hours: 72, text: "Last 3 days" },
  { hours: 168, text: "Last 7 days" },
];

/**
 * The heading of a screen that looks back over a time window (the Brief and Alerts): an optional line above, the title, one
 * sliders button that opens the window in a bottom sheet (the thumb zone), and "Showing the last 24 hours" under it.
 * One component for both screens, and one setting (`windowHours` in settings storage), so a change on either is the change on both.
 * With no `title` it is the Brief's own: "Today's Highlights", or "Highlights: last 3 days".
 */
export function WindowHeader({ title, above, children }: { title?: string; above?: ReactNode; children?: ReactNode }) {
  const configState = useJson<AppConfig>("/data/config.json");
  const settings = useSettings(configState.kind === "ready" ? configState.data : null);
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const hours = settings.windowHours;

  return (
    <section aria-labelledby={titleId} className="pt-4">
      {above}
      <div className="flex items-start justify-between gap-3">
        <h1 id={titleId} className="min-w-0 text-2xl font-semibold tracking-tight">
          {title ?? highlightsTitle(hours)}
        </h1>
        <button
          type="button"
          aria-label="Change the time window"
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
          className="-mr-1 inline-flex size-11 shrink-0 items-center justify-center rounded-full border border-line bg-surface text-ink-soft"
        >
          <SlidersIcon size={20} />
        </button>
      </div>
      <p className="mt-0.5 text-sm text-ink-faint">Showing the last {windowLabel(hours)}</p>
      {children}

      <BottomSheet open={open} onClose={() => setOpen(false)} title="Time window">
        <div role="radiogroup" aria-label="Time window" className="space-y-2">
          {OPTIONS.map((option) => {
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
                className={`flex min-h-12 w-full items-center justify-between rounded-2xl border px-4 text-left text-sm font-medium ${selected ? "border-accent bg-backdrop" : "border-line"}`}
              >
                {option.text}
                {selected && (
                  <span aria-hidden="true" className="text-accent">
                    ✓
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <p className="mt-3 text-xs leading-5 text-ink-faint">One setting for the Brief and Alerts. It is also under You, in Preferences.</p>
      </BottomSheet>
    </section>
  );
}
