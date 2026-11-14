"use client";

import Link from "next/link";
import { useState } from "react";
import { SignalCard } from "@/components/alerts/SignalCard";
import { FilingCard } from "@/components/brief/FilingCard";
import { WindowPicker } from "@/components/brief/WindowPicker";
import { filingAlerts, signalAlerts } from "@/lib/alerts";
import { GROUP_LIMIT, whenLabel, windowLabel } from "@/lib/brief";
import { updateSettings, useSettings } from "@/lib/settings";
import type { AppConfig, Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";

function ShowMore({ hidden, onClick }: { hidden: number; onClick: () => void }) {
  if (hidden <= 0) return null;
  return (
    <button type="button" onClick={onClick} className="mt-3 min-h-11 w-full rounded-full border border-line text-sm font-medium">
      Show {hidden} more
    </button>
  );
}

export function AlertsScreen() {
  const briefState = useJson<Brief>("/data/brief.json");
  const configState = useJson<AppConfig>("/data/config.json");
  const settings = useSettings(configState.kind === "ready" ? configState.data : null);
  const [allSignals, setAllSignals] = useState(false);
  const [allFilings, setAllFilings] = useState(false);

  if (briefState.kind === "loading") {
    return <div className="h-64 animate-pulse rounded-2xl bg-line" aria-label="Loading your alerts" />;
  }
  if (briefState.kind === "error") {
    return (
      <section className="rounded-2xl border border-line p-5">
        <h2 className="text-base font-medium text-watch">Your alerts are unavailable right now</h2>
        <p className="mt-1 text-sm leading-6 text-ink-soft">The data file could not be loaded. Check your connection and reload.</p>
      </section>
    );
  }

  const brief = briefState.data;
  const signals = signalAlerts(brief, settings);
  const filings = filingAlerts(brief, settings);
  const total = signals.length + filings.length;
  const kinds = Object.values(settings.alertCategories).filter(Boolean).length;
  const shownSignals = allSignals ? signals : signals.slice(0, GROUP_LIMIT);
  const shownFilings = allFilings ? filings : filings.slice(0, GROUP_LIMIT);

  return (
    <div>
      <WindowPicker value={settings.windowHours} onChange={(windowHours) => updateSettings({ windowHours })} />

      <p className="mt-5 text-lg font-semibold tracking-tight">
        {total === 0 ? "No alerts" : `${total} ${total === 1 ? "alert" : "alerts"}`}
        <span className="block text-sm font-normal text-ink-soft">in the last {windowLabel(settings.windowHours)}</span>
      </p>

      <p className="mt-3 rounded-xl bg-line px-3 py-2 text-xs leading-5 text-ink-soft">
        Your lines: price moves above ±{settings.priceMovePct}%, volume above {settings.volumeMultiple}× its 20-day average,{" "}
        {kinds} kinds of filing
        {settings.mutedSymbols.length > 0 && `, ${settings.mutedSymbols.length} muted`}.{" "}
        <Link href="/settings" className="font-medium text-ink underline underline-offset-2">
          Change them
        </Link>
      </p>

      {signals.length > 0 && (
        <section aria-label="Price and volume" className="mt-8">
          <h2 className="flex items-baseline gap-2 text-sm font-semibold">
            Price and volume <span className="text-xs font-normal text-ink-faint">{signals.length}</span>
          </h2>
          <p className="mt-0.5 text-xs text-ink-faint">Unusual end-of-day moves, risks first</p>
          <div className="mt-3 flex flex-col gap-3">
            {shownSignals.map((alert) => (
              <SignalCard
                key={`${alert.symbol}-${alert.session.day}`}
                alert={alert}
                priceMovePct={settings.priceMovePct}
                volumeMultiple={settings.volumeMultiple}
              />
            ))}
          </div>
          <ShowMore hidden={signals.length - shownSignals.length} onClick={() => setAllSignals(true)} />
        </section>
      )}

      {filings.length > 0 && (
        <section aria-label="Filings you asked about" className="mt-8">
          <h2 className="flex items-baseline gap-2 text-sm font-semibold">
            Filings you asked about <span className="text-xs font-normal text-ink-faint">{filings.length}</span>
          </h2>
          <p className="mt-0.5 text-xs text-ink-faint">The kinds of filing you switched on in Settings</p>
          <div className="mt-3 flex flex-col gap-3">
            {shownFilings.map((item) => (
              <FilingCard key={item.id} item={item} referenceIso={brief.generated_at} size="md" />
            ))}
          </div>
          <ShowMore hidden={filings.length - shownFilings.length} onClick={() => setAllFilings(true)} />
        </section>
      )}

      <p className="mt-10 text-center text-sm text-ink-soft">
        <span className="font-semibold text-good" aria-hidden="true">
          ✓
        </span>{" "}
        You&apos;re all caught up
        <span className="mt-1 block text-xs text-ink-faint">Checked {whenLabel(brief.generated_at, brief.generated_at)}</span>
      </p>
      <p className="mx-auto mt-4 max-w-xs text-center text-xs leading-5 text-ink-faint">
        FINN checks when you open it. Push notifications to your phone are not part of this version.
      </p>
    </div>
  );
}
