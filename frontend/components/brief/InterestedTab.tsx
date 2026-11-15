"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { VerdictBar } from "@/components/ui/Charts";
import { StarIcon } from "@/components/ui/Icons";
import { PreviewBadge } from "@/components/ui/Preview";
import { Avatar, PriceChip } from "@/components/ui/Price";
import { toggleFollow, useFollow } from "@/lib/follow";
import { shortName } from "@/lib/headline";
import { peopleFromBrief, plainName, type PersonEntry } from "@/lib/people";
import { dateLabel, type IndexEntry, type ResearchIndex, type ResearchRecord } from "@/lib/research";
import type { Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";
import { useCompanyPrices } from "@/lib/useSessions";

const PEOPLE_SHOWN = 5;

function FollowStar({ name, on, onToggle }: { name: string; on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={on ? `Following ${name}. Tap to stop` : `Follow ${name}`}
      onClick={onToggle}
      className={`-mr-2 inline-flex size-11 shrink-0 items-center justify-center rounded-full ${on ? "text-watch" : "text-ink-faint"}`}
    >
      <StarIcon filled={on} size={20} />
    </button>
  );
}

/** One company the reader is interested in: price, what management promised and kept, the way into the research. */
function CompanyRow({ entry, onInvest }: { entry: IndexEntry; onInvest: (name: string) => void }) {
  const prices = useCompanyPrices(entry.symbol);
  const record = useJson<ResearchRecord>(`/data/research/${encodeURIComponent(entry.symbol)}.json`);
  const follow = useFollow();
  const followed = follow.companies.includes(entry.symbol);
  const name = shortName(entry.name);
  const card = record.kind === "ready" && record.data.status === "ready" ? record.data.scorecard : null;

  return (
    <article className="rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <Avatar symbol={entry.symbol} name={entry.name} size={38} />
          <div className="min-w-0">
            <h3 className="text-base font-semibold leading-tight">{name}</h3>
            <p className="text-xs text-ink-faint">{entry.symbol}</p>
          </div>
        </div>
        <div className="flex items-start gap-1">
          <PriceChip sessions={prices.sessions} generatedAt={prices.generatedAt} />
          <FollowStar name={name} on={followed} onToggle={() => toggleFollow("companies", entry.symbol)} />
        </div>
      </div>

      <div className="mt-3">
        {card ? (
          <>
            <VerdictBar card={card} />
            <p className="mt-1.5 text-xs text-ink-faint">
              Promise Tracker{card.as_of_call ? `, as of the ${card.as_of_call} call` : ""}
            </p>
          </>
        ) : (
          <p className="text-xs leading-5 text-ink-soft">
            {entry.status === "statements_only" ? "No verdict yet: what management said is in the research." : "Open the research to read the filings."}
          </p>
        )}
      </div>

      <div className="mt-3 flex gap-2">
        <Link
          href={`/research?symbol=${encodeURIComponent(entry.symbol)}`}
          className="inline-flex min-h-11 flex-1 items-center justify-center rounded-full border border-line text-sm font-medium"
        >
          Open research
        </Link>
        <button
          type="button"
          onClick={() => onInvest(name)}
          className="inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-ink text-sm font-medium text-surface"
        >
          Invest <PreviewBadge className="border-surface/60 text-surface" />
        </button>
      </div>
    </article>
  );
}

function PersonRow({ person, on }: { person: PersonEntry; on: boolean }) {
  return (
    <li className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-3">
      <Avatar symbol={person.symbol} name={plainName(person.name)} size={36} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{person.name}</p>
        <p className="truncate text-xs text-ink-soft">
          {person.role ? `${person.role} · ` : ""}
          {person.action}
        </p>
        <p className="text-xs text-ink-faint">
          {person.company} · from the filing of {dateLabel(person.filed)}
        </p>
      </div>
      <button
        type="button"
        aria-pressed={on}
        aria-label={on ? `Following ${person.name}. Tap to stop` : `Follow ${person.name}`}
        onClick={() => toggleFollow("people", person.id)}
        className={`inline-flex min-h-11 shrink-0 items-center rounded-full border px-4 text-xs font-semibold ${on ? "border-ink bg-ink text-surface" : "border-line text-ink-soft"}`}
      >
        {on ? "Following" : "Follow"}
      </button>
    </li>
  );
}

/** People named in real management-change filings in the brief. Following is stored here only: it triggers nothing yet. */
function People() {
  const brief = useJson<Brief>("/data/brief.json");
  const follow = useFollow();
  const [all, setAll] = useState(false);
  const people = useMemo(() => (brief.kind === "ready" ? peopleFromBrief(brief.data) : []), [brief]);
  if (brief.kind !== "ready" || people.length === 0) return null;
  const shown = all ? people : people.slice(0, PEOPLE_SHOWN);
  return (
    <section aria-labelledby="people-title" className="mt-8">
      <div className="flex items-center gap-2">
        <h2 id="people-title" className="text-sm font-semibold">
          People to follow
        </h2>
        <PreviewBadge />
      </div>
      <p className="mt-1 text-xs leading-5 text-ink-soft">
        Named in real management-change filings. Alerts for followed people aren&apos;t connected yet: the plan is to track them through insider-trading and management-change filings.
      </p>
      <ul className="mt-3 space-y-2">
        {shown.map((p) => (
          <PersonRow key={p.id} person={p} on={follow.people.includes(p.id)} />
        ))}
      </ul>
      {people.length > PEOPLE_SHOWN && !all && (
        <button type="button" onClick={() => setAll(true)} className="mt-2 inline-flex min-h-11 items-center text-xs font-medium text-ink-soft underline underline-offset-2">
          Show all {people.length}
        </button>
      )}
    </section>
  );
}

/** The Interested tab: the companies the reader is researching, and the people worth following. A concept preview on real data. */
export function InterestedTab() {
  const index = useJson<ResearchIndex>("/data/research/index.json");
  const follow = useFollow();
  const [investIn, setInvestIn] = useState<string | null>(null);

  if (index.kind === "loading") return <div className="h-48 animate-pulse rounded-2xl bg-line" aria-label="Loading" />;
  if (index.kind === "error") {
    return (
      <section className="rounded-2xl border border-line p-5">
        <h2 className="text-base font-medium text-watch">The list is unavailable right now</h2>
        <p className="mt-1 text-sm leading-6 text-ink-soft">The data file could not be loaded. Check your connection and reload.</p>
      </section>
    );
  }
  const companies = [...index.data.companies].sort((a, b) => Number(follow.companies.includes(b.symbol)) - Number(follow.companies.includes(a.symbol)));
  return (
    <div>
      <p className="text-xs leading-5 text-ink-soft">Companies you are researching. Tap the star to follow one; it stays in this browser.</p>
      <div className="mt-3 space-y-3">
        {companies.map((entry) => (
          <CompanyRow key={entry.symbol} entry={entry} onInvest={setInvestIn} />
        ))}
      </div>

      <People />

      <BottomSheet open={investIn !== null} onClose={() => setInvestIn(null)} title={investIn ? `Invest in ${investIn}` : "Invest"}>
        <div className="space-y-3 text-sm leading-6">
          <PreviewBadge />
          <p className="font-medium">Coming soon: invest through a SEBI-registered broker partner.</p>
          <p className="text-ink-soft">This is a concept. Nothing here places an order, holds money or gives advice.</p>
        </div>
      </BottomSheet>
    </div>
  );
}
