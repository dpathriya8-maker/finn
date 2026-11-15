"use client";

import { FilingRow, type CardSize } from "@/components/brief/FilingRow";
import { useBriefPrices } from "@/components/brief/PricesContext";
import { Avatar, PriceLine } from "@/components/ui/Price";
import type { CompanyGroup } from "@/lib/brief";
import { shortName } from "@/lib/headline";
import { holdingLine, useInvested } from "@/lib/invested";
import { priceView } from "@/lib/prices";

/**
 * One company, once: its badge, short name and price on line 1, then each of its filings in the window under it, most
 * important first. The name is the only part that gives way (it is cut with an ellipsis) when the screen is narrow; the badge
 * and the price chip keep their size.
 */
export function CompanyCard({ group, referenceIso, size }: { group: CompanyGroup; referenceIso: string; size: CardSize }) {
  const { sessions, generatedAt } = useBriefPrices(group.symbol);
  const name = shortName(group.company);
  const amount = useInvested()[group.symbol];
  const view = priceView(sessions, generatedAt);
  const holding = amount && view ? holdingLine(amount, view.changePct) : null;

  return (
    <article aria-label={name} className="relative min-w-0 overflow-hidden rounded-2xl border border-line bg-surface">
      <header className="flex min-w-0 items-center gap-2.5 px-3 pb-1 pt-3">
        <Avatar symbol={group.symbol} name={group.company} size={32} />
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{name}</h3>
        <PriceLine sessions={sessions} generatedAt={generatedAt} />
      </header>
      {holding && (
        <p className="truncate px-3 pb-2 pl-[3.75rem] text-xs tabular-nums text-ink-faint">
          {holding.lead}
          <span className={holding.tone === "good" ? "font-medium text-good" : holding.tone === "bad" ? "font-medium text-bad" : "font-medium"}>{holding.move}</span>
        </p>
      )}
      <div className="divide-y divide-line">
        {group.items.map((item) => (
          <FilingRow key={item.id} item={item} referenceIso={referenceIso} size={size} />
        ))}
      </div>
    </article>
  );
}
