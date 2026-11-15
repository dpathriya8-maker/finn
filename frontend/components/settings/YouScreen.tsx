"use client";

import { useState, type ReactNode } from "react";
import { WindowPicker } from "@/components/brief/WindowPicker";
import { RangeSetting, SwitchRow } from "@/components/settings/controls";
import { PersonIcon } from "@/components/ui/Icons";
import { filingAlerts, signalAlerts } from "@/lib/alerts";
import { windowLabel } from "@/lib/brief";
import { hueFor } from "@/lib/headline";
import { nameInitials, setProfileName, useProfileName } from "@/lib/profile";
import { resetSettings, setAlertCategory, setMuted, updateSettings, useSettings } from "@/lib/settings";
import type { AppConfig, Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";

function Card({ children }: { children: ReactNode }) {
  return <div className="mt-3 divide-y divide-line rounded-2xl border border-line bg-surface">{children}</div>;
}

/** A top-level section of this screen: a heading, a line that says what it is for, then its content. */
function Section({ id, title, hint, count, children }: { id: string; title: string; hint: string; count?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="mt-10 scroll-mt-4">
      <h2 id={`${id}-title`} className="flex items-baseline gap-2 text-lg font-semibold tracking-tight">
        {title}
        {count && <span className="text-xs font-normal text-ink-faint">{count}</span>}
      </h2>
      <p className="mt-0.5 text-xs leading-5 text-ink-faint">{hint}</p>
      {children}
    </section>
  );
}

/**
 * Who you are, without an account: an initials circle and an optional name. The name lives in this browser only and is used
 * for the Brief's greeting. The field keeps its own draft while you type (so a space between two words survives), and saves
 * the tidied name as you go.
 */
function Profile() {
  const name = useProfileName();
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? name;
  const initials = nameInitials(shown);

  return (
    <section aria-label="Your name" className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-4">
      <span
        className={`inline-flex size-14 shrink-0 items-center justify-center rounded-full text-lg font-semibold ${initials ? "avatar" : "bg-line text-ink-soft"}`}
        style={{ ["--h" as string]: hueFor(shown || "you") }}
        aria-hidden="true"
      >
        {initials || <PersonIcon size={26} />}
      </span>
      <div className="min-w-0 flex-1">
        <label htmlFor="your-name" className="block text-sm font-medium">
          What should we call you?
        </label>
        <input
          id="your-name"
          type="text"
          value={shown}
          maxLength={40}
          autoComplete="off"
          autoCapitalize="words"
          enterKeyHint="done"
          placeholder="Your name (optional)"
          onChange={(event) => {
            setDraft(event.target.value);
            setProfileName(event.target.value);
          }}
          onBlur={() => setDraft(null)}
          className="mt-1.5 min-h-11 w-full min-w-0 rounded-xl border border-line bg-page px-3 text-base placeholder:text-ink-faint"
        />
        <p className="mt-1.5 text-xs leading-5 text-ink-faint">Only used for the greeting on your Brief.</p>
      </div>
    </section>
  );
}

const PRINCIPLES = [
  { lead: "Bad news first.", text: "Risks and misses rank above good news, and every card says why it ranked where it did." },
  { lead: "Every claim has a source.", text: "Numbers and quotes link back to the filing and the page. If the documents do not say it, FINN says so." },
  { lead: "No gamification.", text: "No streaks, scores or badges. The Brief ends, and tells you when you are all caught up." },
];

const SOURCES = [
  { lead: "Announcements", text: "company filings on BSE, with NSE as a fallback" },
  { lead: "Prices", text: "end-of-day prices and volumes from Yahoo Finance" },
  { lead: "Research", text: "only annual reports and earnings-call transcripts filed by the company. No news, no broker notes" },
];

export function YouScreen() {
  const briefState = useJson<Brief>("/data/brief.json");
  const configState = useJson<AppConfig>("/data/config.json");
  const config = configState.kind === "ready" ? configState.data : null;
  const settings = useSettings(config);

  if (configState.kind === "loading" || briefState.kind === "loading") {
    return <div className="h-64 animate-pulse rounded-2xl bg-line" aria-label="Loading your settings" />;
  }
  if (!config || briefState.kind !== "ready") {
    return (
      <>
        <Profile />
        <section className="mt-6 rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-base font-medium text-watch">Your settings are unavailable right now</h2>
          <p className="mt-1 text-sm leading-6 text-ink-soft">The data files could not be loaded. Check your connection and reload.</p>
        </section>
      </>
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
      <Profile />

      <Section
        id="muted"
        title="My portfolio"
        count={`${companies.length} companies${muted.size > 0 ? ` · ${muted.size} muted` : ""}`}
        hint="The companies FINN watches for you. Switch one on to mute it: a muted company is left out of the Brief and of Alerts."
      >
        <Card>
          {companies.map((c) => (
            <SwitchRow
              key={c.symbol}
              label={c.name}
              ariaLabel={`Mute ${c.name}`}
              hint={`${c.symbol} · ${c.sector}${muted.has(c.symbol) ? " · muted" : ""}`}
              checked={muted.has(c.symbol)}
              onChange={(on) => setMuted(c.symbol, on)}
            />
          ))}
        </Card>
      </Section>

      <Section id="preferences" title="Preferences" hint="You decide what counts as news. Changes apply at once.">
        <h3 className="mt-4 text-sm font-semibold">Time window</h3>
        <p className="mt-0.5 text-xs text-ink-faint">How far back the Brief and Alerts look. The same window on both.</p>
        <div className="mt-3">
          <WindowPicker value={settings.windowHours} onChange={(windowHours) => updateSettings({ windowHours })} />
        </div>

        <h3 className="mt-7 text-sm font-semibold">Unusual moves</h3>
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
          With these lines, <strong>{signals}</strong> price or volume {signals === 1 ? "alert" : "alerts"} and <strong>{filings}</strong>{" "}
          {filings === 1 ? "filing" : "filings"} in the last {windowLabel(settings.windowHours)}.
        </p>

        <h3 className="mt-7 text-sm font-semibold">Filings that alert you</h3>
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

        <h3 className="mt-7 text-sm font-semibold">Language</h3>
        <div className="mt-3 flex min-h-14 items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-4 py-2">
          <span className="min-w-0">
            <span className="block text-sm font-medium">English</span>
            <span className="block text-xs leading-5 text-ink-faint">The only language today. Others are planned, not built.</span>
          </span>
          <span aria-hidden="true" className="shrink-0 text-sm font-semibold">
            ✓
          </span>
        </div>
      </Section>

      <Section id="how" title="How FINN works" hint="Three rules it keeps.">
        <ol className="mt-3 space-y-3">
          {PRINCIPLES.map((p, i) => (
            <li key={p.lead} className="flex gap-3 rounded-2xl border border-line bg-surface p-4">
              <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-backdrop text-xs font-semibold text-ink-soft" aria-hidden="true">
                {i + 1}
              </span>
              <p className="min-w-0 text-sm leading-6 text-ink-soft">
                <strong className="font-semibold text-ink">{p.lead}</strong> {p.text}
              </p>
            </li>
          ))}
        </ol>
        <h3 className="mt-6 text-sm font-semibold">Where the data comes from</h3>
        <ul className="mt-2 space-y-1.5 text-xs leading-5 text-ink-soft">
          {SOURCES.map((s) => (
            <li key={s.lead}>
              <strong className="font-semibold text-ink">{s.lead}:</strong> {s.text}.
            </li>
          ))}
        </ul>
      </Section>

      <button
        type="button"
        onClick={resetSettings}
        className="mt-10 min-h-11 w-full rounded-full border border-line bg-surface text-sm font-medium"
      >
        Reset preferences and muted companies
      </button>
      <p className="mx-auto mt-4 max-w-xs text-center text-xs leading-5 text-ink-faint">
        No account needed. Your settings stay on this phone. FINN keeps nothing about you on a server.
      </p>
    </div>
  );
}
