"use client";

import Link from "next/link";
import { CollapsedRow } from "@/components/brief/CollapsedRow";
import { GroupSection } from "@/components/brief/GroupSection";
import { PortfolioSummary } from "@/components/brief/PortfolioSummary";
import { PricesProvider } from "@/components/brief/PricesContext";
import { companySections, groupItems, selectItems, staleNotes, summaryParts, whenLabel, WINDOWS } from "@/lib/brief";
import { updateSettings, useSettings } from "@/lib/settings";
import type { AppConfig, Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";

export function MorningBrief() {
  const briefState = useJson<Brief>("/data/brief.json");
  const configState = useJson<AppConfig>("/data/config.json");
  const settings = useSettings(configState.kind === "ready" ? configState.data : null);

  if (briefState.kind === "loading") {
    return <div className="h-64 animate-pulse rounded-2xl bg-line" aria-label="Loading your brief" />;
  }
  if (briefState.kind === "error") {
    return (
      <section className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="text-base font-medium text-watch">Your brief is unavailable right now</h2>
        <p className="mt-1 text-sm leading-6 text-ink-soft">The data file could not be loaded. Check your connection and reload.</p>
      </section>
    );
  }

  const brief = briefState.data;
  const hours = settings.windowHours;
  const groups = groupItems(selectItems(brief, hours, settings.mutedSymbols));
  const sections = companySections(groups);
  const companyCount = brief.companies.filter((c) => !settings.mutedSymbols.includes(c.symbol)).length;
  const summary = summaryParts(groups, companyCount);
  const stale = staleNotes(brief);
  const empty = groups.high.length + groups.medium.length + groups.low.length + groups.routine.length === 0;
  const wider = WINDOWS.find((w) => w.hours > hours);

  return (
    <PricesProvider brief={brief}>
      <PortfolioSummary companies={brief.companies} />
      <p className="text-base font-semibold leading-snug tracking-tight" data-testid="summary">
        {summary.map((part, i) => (
          <span key={part.text}>
            {i > 0 && <span className="text-ink-faint"> · </span>}
            <span className={part.tone === "bad" ? "text-bad" : undefined}>{part.text}</span>
          </span>
        ))}
      </p>

      {stale.length > 0 && (
        <p className="mt-3 rounded-xl bg-watch-bg px-3 py-2 text-xs leading-5 text-watch" role="status">
          Some data is older than the rest. {stale.join("; ")}.
        </p>
      )}

      <div className="mt-6">
        <GroupSection
          title="Needs attention"
          hint="Risks and the biggest filings first"
          groups={sections.needs}
          size="lg"
          referenceIso={brief.generated_at}
        />
        <GroupSection
          title="Worth a look"
          hint="Material, but not urgent"
          groups={sections.worth}
          size="md"
          referenceIso={brief.generated_at}
        />
        <CollapsedRow
          label={groups.low.length === 1 ? "lower-priority filing" : "lower-priority filings"}
          hint="Tap to see them"
          items={groups.low}
          referenceIso={brief.generated_at}
        />
        <CollapsedRow
          label={groups.routine.length === 1 ? "routine filing" : "routine filings"}
          hint="Meeting notices, trading windows, newspaper copies and similar"
          items={groups.routine}
          referenceIso={brief.generated_at}
        />
      </div>

      {empty && wider && (
        <button
          type="button"
          onClick={() => updateSettings({ windowHours: wider.hours })}
          className="mt-4 min-h-11 w-full rounded-full border border-line text-sm font-medium"
        >
          Look back {wider.label}
        </button>
      )}

      {settings.mutedSymbols.length > 0 && (
        <p className="mt-6 text-center text-xs text-ink-faint">
          {settings.mutedSymbols.length} {settings.mutedSymbols.length === 1 ? "company is" : "companies are"} muted.{" "}
          <Link href="/settings#muted" className="font-medium text-ink-soft underline underline-offset-2">
            Manage
          </Link>
        </p>
      )}

      <p className="mt-10 pb-2 text-center text-sm text-ink-soft">
        <span className="font-semibold text-good" aria-hidden="true">
          ✓
        </span>{" "}
        You&apos;re all caught up
        <span className="mt-1 block text-xs text-ink-faint">Checked {whenLabel(brief.generated_at, brief.generated_at)}</span>
      </p>
    </PricesProvider>
  );
}
