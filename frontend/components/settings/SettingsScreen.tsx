"use client";

import { WindowPicker } from "@/components/brief/WindowPicker";
import { RangeSetting, SwitchRow } from "@/components/settings/controls";
import { filingAlerts, signalAlerts } from "@/lib/alerts";
import { windowLabel } from "@/lib/brief";
import { resetSettings, setAlertCategory, setMuted, updateSettings, useSettings } from "@/lib/settings";
import type { AppConfig, Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";

function Card({ children }: { children: React.ReactNode }) {
  return <div className="mt-3 divide-y divide-line rounded-2xl border border-line">{children}</div>;
}

export function SettingsScreen() {
  const briefState = useJson<Brief>("/data/brief.json");
  const configState = useJson<AppConfig>("/data/config.json");
  const config = configState.kind === "ready" ? configState.data : null;
  const settings = useSettings(config);

  if (configState.kind === "loading" || briefState.kind === "loading") {
    return <div className="h-64 animate-pulse rounded-2xl bg-line" aria-label="Loading your settings" />;
  }
  if (!config || briefState.kind !== "ready") {
    return (
      <section className="rounded-2xl border border-line p-5">
        <h2 className="text-base font-medium text-watch">Settings are unavailable right now</h2>
        <p className="mt-1 text-sm leading-6 text-ink-soft">The data files could not be loaded. Check your connection and reload.</p>
      </section>
    );
  }

  const brief = briefState.data;
  const signals = signalAlerts(brief, settings).length;
  const filings = filingAlerts(brief, settings).length;
  const categories = [...config.categories].sort((a, b) => b.weight - a.weight);
  const companies = [...brief.companies].sort((a, b) => a.name.localeCompare(b.name));
  const muted = new Set(settings.mutedSymbols);

  return (
    <div>
      <section aria-labelledby="window-title">
        <h2 id="window-title" className="text-sm font-semibold">
          Time window
        </h2>
        <p className="mt-0.5 text-xs text-ink-faint">How far back the Brief and Alerts look</p>
        <div className="mt-3">
          <WindowPicker value={settings.windowHours} onChange={(windowHours) => updateSettings({ windowHours })} />
        </div>
      </section>

      <section aria-labelledby="moves-title" className="mt-8">
        <h2 id="moves-title" className="text-sm font-semibold">
          Unusual moves
        </h2>
        <p className="mt-0.5 text-xs text-ink-faint">When a stock&apos;s end-of-day price or volume counts as unusual</p>
        <Card>
          <RangeSetting
            id="price-move"
            label="Price move"
            unit="%"
            min={1}
            max={15}
            step={0.5}
            value={settings.priceMovePct}
            defaultValue={config.defaults.price_move_pct}
            hint={`Alert when a stock closes more than ${settings.priceMovePct}% up or down on the day.`}
            onChange={(priceMovePct) => updateSettings({ priceMovePct })}
          />
          <RangeSetting
            id="volume-multiple"
            label="Volume"
            unit="×"
            min={1.5}
            max={10}
            step={0.5}
            value={settings.volumeMultiple}
            defaultValue={config.defaults.volume_multiple}
            hint={`Alert when more than ${settings.volumeMultiple} times the usual number of shares trade. Usual is the ${config.defaults.volume_lookback_days}-day average.`}
            onChange={(volumeMultiple) => updateSettings({ volumeMultiple })}
          />
        </Card>
        <p className="mt-3 rounded-xl bg-line px-3 py-2 text-sm leading-6" role="status" data-testid="preview">
          With these lines, <strong>{signals}</strong> price or volume {signals === 1 ? "alert" : "alerts"} and{" "}
          <strong>{filings}</strong> {filings === 1 ? "filing" : "filings"} in the last {windowLabel(settings.windowHours)}.
        </p>
      </section>

      <section aria-labelledby="kinds-title" className="mt-8">
        <h2 id="kinds-title" className="text-sm font-semibold">
          Filings that alert you
        </h2>
        <p className="mt-0.5 text-xs text-ink-faint">Switch on the kinds of announcement you want to hear about. Risks come first.</p>
        <Card>
          {categories.map((c) => (
            <SwitchRow
              key={c.id}
              label={c.label}
              hint={c.why}
              checked={settings.alertCategories[c.id] ?? c.default_alert}
              onChange={(on) => setAlertCategory(c.id, on, c.default_alert)}
            />
          ))}
        </Card>
      </section>

      <section id="muted" aria-labelledby="muted-title" className="mt-8 scroll-mt-4">
        <h2 id="muted-title" className="flex items-baseline gap-2 text-sm font-semibold">
          Muted companies
          <span className="text-xs font-normal text-ink-faint">{muted.size} muted</span>
        </h2>
        <p className="mt-0.5 text-xs text-ink-faint">A muted company is left out of the Brief and of Alerts.</p>
        <Card>
          {companies.map((c) => (
            <SwitchRow
              key={c.symbol}
              label={c.name}
              hint={`${c.symbol} · ${c.sector}`}
              checked={muted.has(c.symbol)}
              onChange={(on) => setMuted(c.symbol, on)}
            />
          ))}
        </Card>
      </section>

      <button
        type="button"
        onClick={resetSettings}
        className="mt-8 min-h-11 w-full rounded-full border border-line text-sm font-medium"
      >
        Reset everything to the defaults
      </button>
      <p className="mx-auto mt-4 max-w-xs text-center text-xs leading-5 text-ink-faint">
        Your settings stay on this phone. FINN has no accounts and keeps nothing about you on a server.
      </p>
    </div>
  );
}
