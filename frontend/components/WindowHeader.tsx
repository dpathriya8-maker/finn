"use client";

import { useId, useState, type ReactNode } from "react";
import { DataAsOf } from "@/components/DataAsOf";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { SlidersIcon } from "@/components/ui/Icons";
import { highlightsTitle, windowLabel, WINDOWS } from "@/lib/brief";
import { updateSettings } from "@/lib/settings";
import { useWindow } from "@/lib/useWindow";

const OPTIONS = [
  { hours: 24, text: "Last 24 hours" },
  { hours: 72, text: "Last 3 days" },
  { hours: 168, text: "Last 7 days" },
];

/**
 * The heading of a screen that looks back over a time window (the Brief and Alerts): an optional line above, the title, one
 * sliders button that opens the window in a bottom sheet (the thumb zone), and what is being shown under it.
 * One component for both screens, and one setting (`windowHours` in settings storage), so a change on either is the change on both.
 * With no `title` it is the Brief's own: "Today's Highlights", or "Highlights: last 3 days".
 *
 * Counted from the data's own time, never the device clock. If the data is more than a day older than the device's clock the title
 * becomes "Latest highlights" (`staleTitle`) and the first line is "Data as of ...", so an old file is never passed off as today.
 * On the Brief (`widen`), while the reader has not picked a window and the default holds nothing material, it looks back further;
 * the heading then simply names the wider window, and the Brief says why under the tabs (a sentence added up here after the data
 * loaded would push the whole page down).
 */
export function WindowHeader({
  title,
  staleTitle = "Latest highlights",
  widen = false,
  above,
  children,
}: {
  title?: string;
  staleTitle?: string;
  widen?: boolean;
  above?: ReactNode;
  children?: ReactNode;
}) {
  const win = useWindow(widen);
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const hours = win.hours;
  const showing = `Showing the last ${windowLabel(hours)}`;

  return (
    <section aria-labelledby={titleId} className="pt-4">
      {above}
      <div className="flex items-start justify-between gap-3">
        <h1 id={titleId} className="min-w-0 text-2xl font-semibold tracking-tight">
          {win.stale ? staleTitle : (title ?? highlightsTitle(hours))}
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
      {win.stale ? (
        <>
          <div className="mt-0.5 text-sm" data-testid="data-as-of">
            <DataAsOf stale />
          </div>
          <p className="text-sm text-ink-faint">{showing} before then</p>
        </>
      ) : (
        <>
          <p className="mt-0.5 text-sm text-ink-faint">
            {showing}
          </p>
          <div className="text-sm text-ink-soft" data-testid="data-as-of">
            <DataAsOf />
          </div>
        </>
      )}
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
