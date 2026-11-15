"use client";

import Link from "next/link";
import { useId, useMemo, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { TONE } from "@/components/brief/tone";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { VerdictBar } from "@/components/ui/Charts";
import { BarChartIcon, StarIcon } from "@/components/ui/Icons";
import { PreviewBadge } from "@/components/ui/Preview";
import { Avatar, PriceLine, PriceTrend } from "@/components/ui/Price";
import { toggleFollow, useFollow } from "@/lib/follow";
import { shortName } from "@/lib/headline";
import { peopleFromBrief, plainName, type PersonEntry } from "@/lib/people";
import { dateLabel, promiseCounts, promiseHeadline, scorecardTone, type IndexEntry, type ResearchIndex, type ResearchRecord } from "@/lib/research";
import type { Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";
import { useCompanyPrices } from "@/lib/useSessions";

const PEOPLE_SHOWN = 5;

/**
 * One company the reader is researching, in the same three lines as a filing:
 *   line 1  badge, short name, price chip
 *   line 2  what the Promise Tracker says, bold
 *   line 3  small and grey: icon, "Promises", the counts (bad news first), and the tone
 * The verdict bar, the way into the research, Follow and Invest are one tap away.
 */
function CompanyRow({ entry, onInvest }: { entry: IndexEntry; onInvest: (name: string) => void }) {
  const prices = useCompanyPrices(entry.symbol);
  const record = useJson<ResearchRecord>(`/data/research/${encodeURIComponent(entry.symbol)}.json`);
  const follow = useFollow();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const followed = follow.companies.includes(entry.symbol);
  const name = shortName(entry.name);
  const card = record.kind === "ready" && record.data.status === "ready" ? record.data.scorecard : null;
  const tone = TONE[scorecardTone(card)];

  return (
    <article aria-label={name} className="relative min-w-0 overflow-hidden rounded-2xl border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className={`block min-h-11 w-full min-w-0 border-l-4 px-3 py-3 text-left ${card && scorecardTone(card) !== "neutral" ? tone.border : "border-l-transparent"}`}
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <Avatar symbol={entry.symbol} name={entry.name} size={32} />
          <span className="flex min-w-0 flex-1 items-center gap-1.5">
            <span className="truncate text-sm font-semibold text-ink">{name}</span>
            {followed && (
              <span className="shrink-0 text-watch" role="img" aria-label="Following">
                <StarIcon filled size={12} />
              </span>
            )}
          </span>
          <PriceLine sessions={prices.sessions} generatedAt={prices.generatedAt} />
        </span>
        <span className="mt-2 line-clamp-2 break-words text-base font-semibold leading-snug">{promiseHeadline(card, entry.status)}</span>
        <span className="mt-1 flex min-w-0 items-center gap-1.5 text-xs leading-5 text-ink-faint">
          <span className="shrink-0">
            <BarChartIcon size={14} />
          </span>
          <span className="shrink-0 whitespace-nowrap font-medium text-ink-soft">Promises</span>
          <span className="min-w-0 flex-1 truncate">
            {card ? promiseCounts(card) : entry.status === "statements_only" ? "What management said is in the research" : "Open the research to read the filings"}
          </span>
          {tone.tag && card && <span className={`shrink-0 whitespace-nowrap rounded px-1.5 font-medium ${tone.chip}`}>{tone.tag}</span>}
          <span className="shrink-0">
            <Chevron open={open} />
          </span>
        </span>
      </button>

      {open && (
        <div id={panelId} className="min-w-0 border-t border-line px-3 py-3">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <p className="min-w-0 truncate text-xs text-ink-faint">{entry.name} ({entry.symbol})</p>
            <PriceTrend sessions={prices.sessions} generatedAt={prices.generatedAt} />
          </div>
          {card && (
            <div className="mt-3">
              <VerdictBar card={card} />
              <p className="mt-1.5 text-xs text-ink-faint">Promise Tracker{card.as_of_call ? `, as of the ${card.as_of_call} call` : ""}</p>
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Link
              href={`/research?symbol=${encodeURIComponent(entry.symbol)}`}
              className="inline-flex min-h-11 min-w-0 flex-1 items-center justify-center rounded-full border border-line text-sm font-medium"
            >
              Open research
            </Link>
            <button
              type="button"
              aria-pressed={followed}
              onClick={() => toggleFollow("companies", entry.symbol)}
              className={`inline-flex min-h-11 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-full border text-sm font-medium ${followed ? "border-accent bg-backdrop text-accent" : "border-line"}`}
            >
              <StarIcon filled={followed} size={16} />
              {followed ? "Following" : "Follow"}
            </button>
          </div>
          <button
            type="button"
            onClick={() => onInvest(name)}
            className="mt-2 inline-flex min-h-11 w-full items-center justify-center gap-1.5 rounded-full bg-accent-bg text-sm font-medium text-on-accent"
          >
            Invest <PreviewBadge onAccent />
          </button>
        </div>
      )}
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
        className={`inline-flex min-h-11 shrink-0 items-center rounded-full border px-4 text-xs font-semibold ${on ? "border-accent-bg bg-accent-bg text-on-accent" : "border-line text-ink-soft"}`}
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
      <section className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="text-base font-medium text-watch">The list is unavailable right now</h2>
        <p className="mt-1 text-sm leading-6 text-ink-soft">The data file could not be loaded. Check your connection and reload.</p>
      </section>
    );
  }
  const companies = [...index.data.companies].sort((a, b) => Number(follow.companies.includes(b.symbol)) - Number(follow.companies.includes(a.symbol)));
  return (
    <div>
      <p className="text-xs leading-5 text-ink-soft">Companies you are researching. Tap one to open it and follow it; this stays in this browser.</p>
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
