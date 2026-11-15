"use client";

import { useState } from "react";
import { CompanyCard } from "@/components/brief/CompanyCard";
import type { CardSize } from "@/components/brief/FilingRow";
import { SectionBox } from "@/components/ui/SectionBox";
import { GROUP_LIMIT, type CompanyGroup } from "@/lib/brief";

/** One priority section: at most five companies, with the rest one tap away. Renders nothing when empty. */
export function GroupSection({
  title,
  hint,
  groups,
  size,
  referenceIso,
  boxed = true,
}: {
  title: string;
  hint: string;
  groups: CompanyGroup[];
  size: CardSize;
  referenceIso: string;
  /** In its own soft box (the default); false when it sits inside another box, with only its header. */
  boxed?: boolean;
}) {
  const [all, setAll] = useState(false);
  if (groups.length === 0) return null;

  const shown = all ? groups : groups.slice(0, GROUP_LIMIT);
  const hidden = groups.length - shown.length;
  const filings = groups.reduce((sum, g) => sum + g.items.length, 0);
  return (
    <SectionBox title={title} count={String(filings)} hint={hint} bare={!boxed} className={boxed ? "mt-4 first:mt-0" : "mt-6 first:mt-0"}>
      {shown.map((group) => (
        <CompanyCard key={group.symbol} group={group} referenceIso={referenceIso} size={size} />
      ))}
      {hidden > 0 && (
        <button type="button" onClick={() => setAll(true)} className="min-h-11 w-full rounded-full border border-line bg-surface text-sm font-medium">
          Show {hidden} more {hidden === 1 ? "company" : "companies"}
        </button>
      )}
    </SectionBox>
  );
}
