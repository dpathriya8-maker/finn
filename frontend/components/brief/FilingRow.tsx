"use client";

import { useId, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { ManagementCardView } from "@/components/brief/ManagementCardView";
import { ResultsCardView } from "@/components/brief/ResultsCardView";
import { useBriefPrices } from "@/components/brief/PricesContext";
import { TONE } from "@/components/brief/tone";
import { CategoryIcon } from "@/components/ui/Icons";
import { PriceTrend } from "@/components/ui/Price";
import { whenLabel } from "@/lib/brief";
import { filingHeadline } from "@/lib/headline";
import { shortCategory, shortWhy } from "@/lib/labels";
import { setMuted } from "@/lib/settings";
import type { Item } from "@/lib/types";

// Size follows importance.
const HEADLINE = {
  lg: "text-base font-semibold leading-snug",
  md: "text-[0.9375rem] font-semibold leading-snug",
  sm: "text-sm font-medium leading-snug",
} as const;

export type CardSize = keyof typeof HEADLINE;

function fileSize(kb: number | null): string {
  if (!kb) return "";
  return kb >= 1024 ? `PDF, ${(kb / 1024).toFixed(1)} MB` : `PDF, ${kb} KB`;
}

/**
 * One filing under its company's header, collapsed to two lines (the header is line one):
 *   line 2  the headline, bold
 *   line 3  small and grey: category icon, short label, the one-line reason it ranked here, and the tone
 * Everything else (date, price trend, the results table or the person's profile, the PDF, the full ranking reason,
 * mute) is one tap away. Every flex child that can be long has `min-w-0`, and the short label and the tone never shrink,
 * so nothing here can be wider than the screen.
 */
export function FilingRow({ item, referenceIso, size }: { item: Item; referenceIso: string; size: CardSize }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const tone = TONE[item.tone];
  const { sessions, generatedAt } = useBriefPrices(item.symbol);
  const label = [item.raw_category, item.raw_subcategory].filter(Boolean).join(" / ");
  // A card that read the filing says more than the exchange's one-line text; a card that failed leaves that text in place.
  const cardReplacesBody = item.card?.status === "ok" || (item.card?.type === "results" && item.card.status === "partial");

  return (
    <div className={`border-l-4 ${item.tone === "neutral" ? "border-l-transparent" : tone.border}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="block min-h-11 w-full min-w-0 px-3 py-2.5 text-left"
      >
        <span className={`line-clamp-2 break-words ${HEADLINE[size]}`}>{filingHeadline(item)}</span>
        <span className="mt-1 flex min-w-0 items-center gap-1.5 text-xs leading-5 text-ink-faint">
          <span className="shrink-0">
            <CategoryIcon category={item.category} routine={item.routine} />
          </span>
          <span className="shrink-0 whitespace-nowrap font-medium text-ink-soft">{shortCategory(item)}</span>
          <span className="min-w-0 flex-1 truncate">{shortWhy(item)}</span>
          {tone.tag && <span className={`shrink-0 whitespace-nowrap rounded px-1.5 font-medium ${tone.chip}`}>{tone.tag}</span>}
          <span className="shrink-0 text-ink-faint">
            <Chevron open={open} />
          </span>
        </span>
      </button>

      {open && (
        <div id={panelId} className="min-w-0 border-t border-line px-3 py-3">
          <p className="break-words text-xs text-ink-faint">
            <time dateTime={item.published_at}>{whenLabel(item.published_at, referenceIso)}</time> · {item.company} ({item.symbol})
          </p>
          <div className="mt-2">
            <PriceTrend sessions={sessions} generatedAt={generatedAt} />
          </div>
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
          {item.body && !cardReplacesBody && <p className="mt-2 whitespace-pre-line break-words text-sm leading-6 text-ink-soft">{item.body}</p>}
          {item.url && (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex min-h-11 max-w-full items-center rounded-full border border-line px-4 text-sm font-medium"
            >
              Open the filing{item.size_kb ? ` (${fileSize(item.size_kb)})` : ""}
            </a>
          )}
          <p className="mt-3 break-words text-xs leading-5 text-ink-faint">
            Why it is here: {item.why}. Ranked {item.priority} out of 100. Filed on {item.source.toUpperCase()} as “{label || item.category_label}”.
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
    </div>
  );
}
