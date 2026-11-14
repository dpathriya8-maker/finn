"use client";

import { useState } from "react";
import { FilingCard, type CardSize } from "@/components/brief/FilingCard";
import { GROUP_LIMIT } from "@/lib/brief";
import type { Item } from "@/lib/types";

/** One priority group: at most five cards, with the rest one tap away. Renders nothing when empty. */
export function GroupSection({
  title,
  hint,
  items,
  size,
  referenceIso,
}: {
  title: string;
  hint: string;
  items: Item[];
  size: CardSize;
  referenceIso: string;
}) {
  const [all, setAll] = useState(false);
  if (items.length === 0) return null;

  const shown = all ? items : items.slice(0, GROUP_LIMIT);
  const hidden = items.length - shown.length;
  return (
    <section aria-label={title} className="mt-8 first:mt-0">
      <h2 className="flex items-baseline gap-2 text-sm font-semibold">
        {title}
        <span className="text-xs font-normal text-ink-faint">{items.length}</span>
      </h2>
      <p className="mt-0.5 text-xs text-ink-faint">{hint}</p>
      <div className="mt-3 flex flex-col gap-3">
        {shown.map((item) => (
          <FilingCard key={item.id} item={item} referenceIso={referenceIso} size={size} />
        ))}
      </div>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setAll(true)}
          className="mt-3 min-h-11 w-full rounded-full border border-line text-sm font-medium"
        >
          Show {hidden} more
        </button>
      )}
    </section>
  );
}
