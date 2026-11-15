"use client";

import { useId, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { useBecause } from "@/components/follow/BecauseContext";
import { whenLabel } from "@/lib/brief";
import type { Item } from "@/lib/types";

/** A collapsed row such as "12 routine filings": batched so it does not compete for attention. */
export function CollapsedRow({
  label,
  hint,
  items,
  referenceIso,
}: {
  label: string;
  hint: string;
  items: Item[];
  referenceIso: string;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  if (items.length === 0) return null;

  return (
    <section className="mt-8 rounded-2xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-14 w-full items-center justify-between gap-3 px-4 py-2 text-left"
      >
        <span>
          <span className="block text-sm font-semibold">
            {items.length} {label}
          </span>
          <span className="block text-xs text-ink-faint">{hint}</span>
        </span>
        <Chevron open={open} />
      </button>
      {open && (
        <ul id={listId} className="divide-y divide-line border-t border-line">
          {items.map((item) => (
            <CollapsedItem key={item.id} item={item} referenceIso={referenceIso} />
          ))}
        </ul>
      )}
    </section>
  );
}

function CollapsedItem({ item, referenceIso }: { item: Item; referenceIso: string }) {
  const because = useBecause(item.id);
  return (
    <li className="px-4 py-2.5">
      <div className="flex items-baseline justify-between gap-3 text-xs text-ink-faint">
        <span className="font-semibold text-ink-soft">{item.symbol}</span>
        <time dateTime={item.published_at}>{whenLabel(item.published_at, referenceIso)}</time>
      </div>
      <p className="mt-0.5 text-sm leading-5 text-ink-soft">{item.headline}</p>
      {because && (
        <p className="mt-0.5 text-xs leading-5 text-ink-faint" data-testid="because">
          {because}
        </p>
      )}
      {item.url && (
        <a href={item.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex min-h-8 items-center text-xs font-medium underline underline-offset-2">
          Open the filing
        </a>
      )}
    </li>
  );
}
