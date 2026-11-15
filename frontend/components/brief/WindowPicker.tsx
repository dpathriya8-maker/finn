"use client";

import { WINDOWS } from "@/lib/brief";

/** The time window, as a thumb-sized segmented control. */
export function WindowPicker({ value, onChange }: { value: number; onChange: (hours: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Time window" className="grid grid-cols-3 gap-1 rounded-full bg-line p-1">
      {WINDOWS.map((w) => {
        const selected = w.hours === value;
        return (
          <button
            key={w.hours}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(w.hours)}
            className={`min-h-11 rounded-full text-sm font-medium ${
              selected ? "bg-surface font-semibold text-accent shadow-sm" : "text-ink-soft"
            }`}
          >
            {w.label}
          </button>
        );
      })}
    </div>
  );
}
