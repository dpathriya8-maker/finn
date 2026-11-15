"use client";

import { useId, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { ManagementCardView } from "@/components/brief/ManagementCardView";
import { ResultsCardView } from "@/components/brief/ResultsCardView";
import { useBriefPrices } from "@/components/brief/PricesContext";
import { TONE } from "@/components/brief/tone";
import { CategoryIcon } from "@/components/ui/Icons";
import { Avatar, PriceChip } from "@/components/ui/Price";
import { whenLabel } from "@/lib/brief";
import { cardHeadline } from "@/lib/headline";
import { setMuted } from "@/lib/settings";
import type { Item } from "@/lib/types";

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
  const { sessions, generatedAt } = useBriefPrices(item.symbol);
  const label = [item.raw_category, item.raw_subcategory].filter(Boolean).join(" / ");
  // A card that read the filing says more than the exchange's one-line text; a card that failed leaves that text in place.
  const cardReplacesBody = item.card?.status === "ok" || (item.card?.type === "results" && item.card.status === "partial");

  return (
    <article className={`rounded-2xl border border-l-4 border-line ${tone.border} bg-surface`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="block min-h-11 w-full px-4 py-3 text-left"
      >
        <span className="flex items-start justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2.5">
            <Avatar symbol={item.symbol} name={item.company} size={34} />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-ink-soft">{item.symbol}</span>
              <span className="flex items-center gap-1 text-xs text-ink-faint">
                <CategoryIcon category={item.category} routine={item.routine} />
                <span className="truncate">{item.category_label}</span>
              </span>
            </span>
          </span>
          <PriceChip sessions={sessions} generatedAt={generatedAt} />
        </span>
        <span className="mt-2 flex items-center gap-2 text-xs text-ink-faint">
          {tone.tag && <span className={`rounded px-1.5 py-0.5 font-medium ${tone.chip}`}>{tone.tag}</span>}
          <time dateTime={item.published_at}>{whenLabel(item.published_at, referenceIso)}</time>
        </span>
        <span className={`mt-1 block ${HEADLINE[size]}`}>{cardHeadline(item)}</span>
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
          {item.card?.type === "results" && (
            <div className="mt-3">
              <ResultsCardView card={item.card} />
            </div>
          )}
          {item.card?.type === "management" && (
            <div className="mt-3">
              <ManagementCardView card={item.card} />
            </div>
          )}
          {item.body && !cardReplacesBody && <p className="mt-2 whitespace-pre-line text-sm leading-6 text-ink-soft">{item.body}</p>}
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
          <button
            type="button"
            onClick={() => setMuted(item.symbol, true)}
            className="mt-2 inline-flex min-h-11 items-center text-xs font-medium text-ink-soft underline underline-offset-2"
          >
            Mute {item.symbol}
          </button>
        </div>
      )}
    </article>
  );
}
