"use client";

import { useState } from "react";
import { CompanyCard } from "@/components/brief/CompanyCard";
import type { CardSize } from "@/components/brief/FilingRow";
import { GROUP_LIMIT, type CompanyGroup } from "@/lib/brief";

/** One priority section: at most five companies, with the rest one tap away. Renders nothing when empty. */
export function GroupSection({
  title,
  hint,
  groups,
  size,
  referenceIso,
}: {
  title: string;
  hint: string;
  groups: CompanyGroup[];
  size: CardSize;
  referenceIso: string;
}) {
  const [all, setAll] = useState(false);
  if (groups.length === 0) return null;

  const shown = all ? groups : groups.slice(0, GROUP_LIMIT);
  const hidden = groups.length - shown.length;
  const filings = groups.reduce((sum, g) => sum + g.items.length, 0);
  return (
    <section aria-label={title} className="mt-8 first:mt-0">
      <h2 className="flex items-baseline gap-2 text-sm font-semibold">
        {title}
        <span className="text-xs font-normal text-ink-faint">{filings}</span>
      </h2>
      <p className="mt-0.5 text-xs text-ink-faint">{hint}</p>
      <div className="mt-3 flex flex-col gap-3">
        {shown.map((group) => (
          <CompanyCard key={group.symbol} group={group} referenceIso={referenceIso} size={size} />
        ))}
      </div>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setAll(true)}
          className="mt-3 min-h-11 w-full rounded-full border border-line text-sm font-medium"
        >
          Show {hidden} more {hidden === 1 ? "company" : "companies"}
        </button>
      )}
    </section>
  );
}
