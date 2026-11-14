"use client";

import { useId, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { whenLabel } from "@/lib/brief";
import type { Item } from "@/lib/types";

// Full class names so Tailwind can see them. Colour carries meaning only: red bad, amber watch, green good.
const TONE = {
  bad: { border: "border-l-bad", chip: "bg-bad-bg text-bad", tag: "Risk" },
  watch: { border: "border-l-watch", chip: "bg-watch-bg text-watch", tag: "Watch" },
  good: { border: "border-l-good", chip: "bg-good-bg text-good", tag: "Good news" },
  neutral: { border: "border-l-line", chip: "", tag: "" },
} as const;

// Size follows importance.
const HEADLINE = {
  lg: "text-lg font-semibold leading-snug",
  md: "text-base font-semibold leading-snug",
  sm: "text-sm font-medium leading-snug",
} as const;

export type CardSize = keyof typeof HEADLINE;

function fileSize(kb: number | null): string {
  if (!kb) return "";
  return kb >= 1024 ? `PDF, ${(kb / 1024).toFixed(1)} MB` : `PDF, ${kb} KB`;
}

export function FilingCard({ item, referenceIso, size }: { item: Item; referenceIso: string; size: CardSize }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const tone = TONE[item.tone];
  const label = [item.raw_category, item.raw_subcategory].filter(Boolean).join(" / ");

  return (
    <article className={`rounded-2xl border border-l-4 border-line ${tone.border} bg-surface`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="block min-h-11 w-full px-4 py-3 text-left"
      >
        <span className="flex items-center justify-between gap-3 text-xs text-ink-faint">
          <span className="flex items-center gap-2">
            <span className="font-semibold text-ink-soft">{item.symbol}</span>
            {tone.tag && <span className={`rounded px-1.5 py-0.5 font-medium ${tone.chip}`}>{tone.tag}</span>}
          </span>
          <time dateTime={item.published_at}>{whenLabel(item.published_at, referenceIso)}</time>
        </span>
        <span className={`mt-1.5 block ${HEADLINE[size]}`}>{item.headline}</span>
        <span className="mt-1.5 block text-xs leading-5 text-ink-soft">{item.why}</span>
        <span className="mt-2 flex items-center gap-1 text-xs font-medium text-ink-faint">
          {open ? "Hide details" : "Details"}
          <Chevron open={open} />
        </span>
      </button>

      {open && (
        <div id={panelId} className="border-t border-line px-4 py-3">
          <p className="text-xs text-ink-faint">
            {item.company} · {item.category_label}
          </p>
          {item.body && <p className="mt-2 whitespace-pre-line text-sm leading-6 text-ink-soft">{item.body}</p>}
          {item.url && (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex min-h-11 items-center rounded-full border border-line px-4 text-sm font-medium"
            >
              Open the filing{item.size_kb ? ` (${fileSize(item.size_kb)})` : ""}
            </a>
          )}
          <p className="mt-3 text-xs leading-5 text-ink-faint">
            Ranked {item.priority} out of 100. Filed on {item.source.toUpperCase()} as “{label || item.category_label}”.
            {item.merged ? " The board outcome for the same results was folded into this one." : ""}
          </p>
        </div>
      )}
    </article>
  );
}
