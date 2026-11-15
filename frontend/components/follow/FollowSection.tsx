"use client";

import { useId, useMemo, useState } from "react";
import { CollapsedRow } from "@/components/brief/CollapsedRow";
import { GroupSection } from "@/components/brief/GroupSection";
import { PricesProvider } from "@/components/brief/PricesContext";
import { BecauseProvider } from "@/components/follow/BecauseContext";
import { BuildingIcon, CloseIcon, PersonIcon } from "@/components/ui/Icons";
import { companySections, groupItems, selectItems, whenLabel, windowLabel, WINDOWS } from "@/lib/brief";
import { toggleFollow, useFollow, type Follow } from "@/lib/follow";
import { becauseLine, isFollowed, nothingLine, namedPeople, reasonsFor, suggest, topicById, TOPICS, type Reason, type Suggestion } from "@/lib/followMatch";
import { shortName } from "@/lib/headline";
import { updateSettings } from "@/lib/settings";
import type { Brief } from "@/lib/types";

const STORE_KEY = { company: "companies", person: "people", typed: "people", topic: "topics" } as const;

type Chip = { kind: "company" | "person" | "topic"; id: string; label: string };

/** The followed things as chips, in the order companies, people, topics. */
function chipsFor(follow: Follow, nameOf: (symbol: string) => string): Chip[] {
  return [
    ...follow.companies.map((id) => ({ kind: "company" as const, id, label: nameOf(id) })),
    ...follow.people.map((id) => ({ kind: "person" as const, id, label: id })),
    ...follow.topics.flatMap((id) => (topicById(id) ? [{ kind: "topic" as const, id, label: topicById(id)!.label }] : [])),
  ];
}

function KindIcon({ kind }: { kind: Chip["kind"] | Suggestion["kind"] }) {
  if (kind === "company") return <BuildingIcon size={14} />;
  if (kind === "topic") return <span aria-hidden="true" className="text-xs font-semibold">#</span>;
  return <PersonIcon size={14} />;
}

/** One search box: type a company, a person's full name or a topic and tap to follow it. */
function Search({ brief, follow }: { brief: Brief; follow: Follow }) {
  const [query, setQuery] = useState("");
  const inputId = useId();
  const listId = useId();
  const universe = useMemo(() => ({ companies: brief.companies, people: namedPeople(brief.items) }), [brief]);
  const results = useMemo(() => suggest(query, universe), [query, universe]);
  const typing = query.trim().length > 0;

  return (
    <div>
      <label htmlFor={inputId} className="sr-only">
        Follow a company, person or topic
      </label>
      <input
        id={inputId}
        type="text"
        inputMode="search"
        enterKeyHint="search"
        autoComplete="off"
        autoCapitalize="none"
        spellCheck={false}
        value={query}
        placeholder="Follow a company, person or topic"
        aria-controls={listId}
        onChange={(event) => setQuery(event.target.value)}
        className="min-h-11 w-full min-w-0 rounded-full border border-line bg-surface px-4 text-base placeholder:text-ink-faint"
      />
      {typing && (
        <ul id={listId} className="mt-2 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface" data-testid="suggestions">
          {results.map((s) => {
            const on = isFollowed(follow, s.kind, s.id);
            return (
              <li key={`${s.kind}:${s.id}`}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => {
                    toggleFollow(STORE_KEY[s.kind], s.id);
                    setQuery("");
                  }}
                  className="flex min-h-12 w-full min-w-0 items-center gap-3 px-4 py-2 text-left"
                >
                  <span className="shrink-0 text-ink-soft">
                    <KindIcon kind={s.kind} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{s.kind === "typed" ? `Follow “${s.label}”` : s.label}</span>
                    <span className="block truncate text-xs text-ink-faint">{s.detail}</span>
                  </span>
                  <span className={`shrink-0 text-xs font-semibold ${on ? "text-accent" : "text-ink-soft"}`}>{on ? "Following ✓" : "Follow"}</span>
                </button>
              </li>
            );
          })}
          {results.length === 0 && (
            <li className="px-4 py-3 text-sm leading-6 text-ink-soft" role="status">
              No match among the {brief.companies.length} companies FINN follows, or the people and topics in their filings. Any NSE company is next. To follow a person, type their full name.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/** What is followed, each with a way to stop (the × is a full-size tap target). */
function Chips({ chips }: { chips: Chip[] }) {
  return (
    <ul className="flex flex-wrap gap-2" aria-label="What you follow">
      {chips.map((chip) => (
        <li key={`${chip.kind}:${chip.id}`} className="flex min-h-11 max-w-full items-center rounded-full border border-line bg-surface pl-3">
          <span className="mr-1.5 shrink-0 text-ink-soft">
            <KindIcon kind={chip.kind} />
          </span>
          <span className="min-w-0 truncate text-sm font-medium">{chip.label}</span>
          <button
            type="button"
            aria-label={`Stop following ${chip.label}`}
            onClick={() => toggleFollow(STORE_KEY[chip.kind], chip.id)}
            className="ml-1 inline-flex size-11 shrink-0 items-center justify-center rounded-full text-ink-soft"
          >
            <CloseIcon size={14} />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Starter topics for someone who follows nothing yet: tap one to follow it. */
function StarterTopics({ follow }: { follow: Follow }) {
  return (
    <div>
      <p className="text-sm leading-6 text-ink-soft">You are not following anything yet. Search above, or tap a topic to start.</p>
      <ul className="mt-2 flex flex-wrap gap-2" aria-label="Topics to follow">
        {TOPICS.map((topic) => (
          <li key={topic.id}>
            <button
              type="button"
              aria-pressed={follow.topics.includes(topic.id)}
              onClick={() => toggleFollow("topics", topic.id)}
              className="inline-flex min-h-11 items-center rounded-full border border-line bg-surface px-3.5 text-sm font-medium"
            >
              {topic.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The Following feed: filings of the last window (counted back from the data's own time) that match anything followed, in the
 * Brief's own three-line cards with the risks first, each filing once, with a grey line on why it is here. Routine and
 * lower-priority filings are collapsed exactly as on the Brief. A followed thing with no filing in the window says so.
 */
function Feed({ brief, follow, hours, chips }: { brief: Brief; follow: Follow; hours: number; chips: Chip[] }) {
  const nameOf = useMemo(() => new Map(brief.companies.map((c) => [c.symbol, shortName(c.name)])), [brief]);
  const inWindow = useMemo(() => selectItems(brief, hours), [brief, hours]);
  const reasons = useMemo(() => {
    const map = new Map<string, Reason[]>();
    for (const item of inWindow) {
      const r = reasonsFor(item, follow, (symbol) => nameOf.get(symbol) ?? symbol);
      if (r.length > 0) map.set(item.id, r);
    }
    return map;
  }, [inWindow, follow, nameOf]);
  const because = useMemo(() => new Map([...reasons].map(([id, r]) => [id, becauseLine(r)])), [reasons]);
  const matched = useMemo(() => inWindow.filter((item) => reasons.has(item.id)), [inWindow, reasons]);
  const groups = useMemo(() => groupItems(matched), [matched]);
  const sections = useMemo(() => companySections(groups), [groups]);
  const windowText = windowLabel(hours);
  const wider = WINDOWS.find((w) => w.hours > hours);

  // Followed things that no filing in the window matches, said plainly.
  const matchedKeys = new Set([...reasons.values()].flat().map((r) => `${r.kind}:${r.id.toLowerCase()}`));
  const quiet = chips.filter((c) => !matchedKeys.has(`${c.kind}:${c.id.toLowerCase()}`));
  const SHOWN_QUIET = 5;

  return (
    <section aria-label="Following" className="mt-6" data-testid="following-feed">
      <h2 className="flex items-baseline gap-2 text-sm font-semibold">
        Following
        <span className="text-xs font-normal text-ink-faint">
          {matched.length} {matched.length === 1 ? "filing" : "filings"} · last {windowText}
        </span>
      </h2>

      {matched.length > 0 && (
        <PricesProvider brief={brief}>
          <BecauseProvider value={because}>
            <div className="mt-3">
              <GroupSection title="Needs attention" hint="Risks and the biggest filings first" groups={sections.needs} size="lg" referenceIso={brief.generated_at} />
              <GroupSection title="Worth a look" hint="Material, but not urgent" groups={sections.worth} size="md" referenceIso={brief.generated_at} />
              <CollapsedRow label={groups.low.length === 1 ? "lower-priority filing" : "lower-priority filings"} hint="Tap to see them" items={groups.low} referenceIso={brief.generated_at} />
              <CollapsedRow label={groups.routine.length === 1 ? "routine filing" : "routine filings"} hint="Meeting notices, trading windows and similar" items={groups.routine} referenceIso={brief.generated_at} />
            </div>
          </BecauseProvider>
        </PricesProvider>
      )}

      {quiet.length > 0 && (
        <ul className="mt-4 space-y-1.5" data-testid="nothing-lines">
          {quiet.slice(0, SHOWN_QUIET).map((c) => (
            <li key={`${c.kind}:${c.id}`} className="text-sm leading-6 text-ink-soft">
              {nothingLine(c.label, windowText)}
            </li>
          ))}
          {quiet.length > SHOWN_QUIET && <li className="text-xs text-ink-faint">and {quiet.length - SHOWN_QUIET} more with nothing in this window.</li>}
        </ul>
      )}

      {matched.length === 0 && wider && (
        <button type="button" onClick={() => updateSettings({ windowHours: wider.hours })} className="mt-3 min-h-11 w-full rounded-full border border-line text-sm font-medium">
          Look back {wider.label}
        </button>
      )}

      {matched.length > 0 && (
        <p className="mt-8 text-center text-sm text-ink-soft">
          <span className="font-semibold text-good" aria-hidden="true">
            ✓
          </span>{" "}
          You&apos;re all caught up
          <span className="mt-1 block text-xs text-ink-faint">Filings checked {whenLabel(brief.generated_at, brief.generated_at)}</span>
        </p>
      )}
    </section>
  );
}

/**
 * Follow a company, a person or a topic, and see their filings. Following is kept in this browser only. It picks which filings
 * appear here; it sends no push notification. FINN reads filings, not news.
 */
export function FollowSection({ brief, hours, researchMissing }: { brief: Brief; hours: number; researchMissing: boolean }) {
  const follow = useFollow();
  const nameOf = useMemo(() => new Map(brief.companies.map((c) => [c.symbol, shortName(c.name)])), [brief]);
  const chips = chipsFor(follow, (symbol) => nameOf.get(symbol) ?? symbol);

  return (
    <section aria-label="Follow" data-testid="follow-section">
      <Search brief={brief} follow={follow} />
      <div className="mt-3">{chips.length > 0 ? <Chips chips={chips} /> : <StarterTopics follow={follow} />}</div>
      {chips.length > 0 && <Feed brief={brief} follow={follow} hours={hours} chips={chips} />}
      <p className="mt-6 text-xs leading-5 text-ink-faint" data-testid="follow-note">
        FINN follows filings from the {brief.companies.length} companies it tracks. Any NSE company is next.
        {researchMissing ? " The filings of the research companies are not available right now." : ""}
      </p>
    </section>
  );
}
