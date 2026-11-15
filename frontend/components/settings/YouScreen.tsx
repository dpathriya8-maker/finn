"use client";

import { useState, type ReactNode } from "react";
import { WindowPicker } from "@/components/brief/WindowPicker";
import { RangeSetting, SwitchRow } from "@/components/settings/controls";
import Link from "next/link";
import { PersonIcon } from "@/components/ui/Icons";
import { filingAlerts, signalAlerts } from "@/lib/alerts";
import { windowLabel } from "@/lib/brief";
import { hueFor, shortName } from "@/lib/headline";
import {
  applySample,
  arrowInrPct,
  clearSample,
  directionOf,
  formatInputNumber,
  formatInr,
  hasOwnEntries,
  hasSample,
  parseAmountInput,
  parsePriceInput,
  position,
  sampleHoldings,
  setHolding,
  totalInvested,
  useInvested,
  type Holding,
  type ParsedInput,
} from "@/lib/invested";
import { priceView } from "@/lib/prices";
import type { ResearchIndex } from "@/lib/research";
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

/** One number box: shows Indian grouping at rest, plain digits while you type, and says so when what you typed is not a number. */
function NumberField({
  id,
  label,
  saved,
  parse,
  onSave,
  error,
  placeholder,
}: {
  id: string;
  label: string;
  saved: number | undefined;
  parse: (text: string) => ParsedInput;
  onSave: (value: number | null) => void;
  error: string;
  placeholder: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? (saved !== undefined ? formatInputNumber(saved) : "");
  const invalid = !parse(shown).valid;
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="block text-xs font-medium text-ink-soft">
        {label}
      </label>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        enterKeyHint="done"
        autoComplete="off"
        value={shown}
        placeholder={placeholder}
        aria-invalid={invalid}
        aria-describedby={invalid ? `${id}-error` : undefined}
        onFocus={() => setDraft(saved !== undefined ? String(saved) : "")}
        onChange={(event) => {
          setDraft(event.target.value);
          const parsed = parse(event.target.value);
          if (parsed.valid) onSave(parsed.value);
        }}
        onBlur={() => setDraft(null)}
        className={`mt-1 min-h-11 w-full min-w-0 rounded-xl border bg-page px-3 text-right text-base tabular-nums placeholder:text-ink-faint ${invalid ? "border-bad" : "border-line"}`}
      />
      {invalid && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-xs text-bad">
          {error}
        </p>
      )}
    </div>
  );
}

/** One company's money: how much was put in, and optionally what was paid per share. Validated as you type, kept on this phone. */
function HoldingRow({
  symbol,
  name,
  saved,
  close,
  prevClose,
  changePct,
}: {
  symbol: string;
  name: string;
  saved: Holding | undefined;
  close: number | null;
  prevClose: number | null;
  changePct: number;
}) {
  const mine = position(symbol, saved, close === null ? null : { close, prevClose, changePct });
  const tone = mine?.pnl == null ? "flat" : directionOf(mine.pnl);
  return (
    <div className="min-w-0 px-4 py-3">
      <p className="flex min-w-0 items-center gap-2 text-sm font-medium">
        <span className="min-w-0 truncate">{name}</span>
        {saved?.sample && <span className="shrink-0 rounded bg-backdrop px-1.5 text-xs font-medium text-ink-soft">Sample</span>}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <NumberField
          id={`amount-${symbol}`}
          label="Amount invested (₹)"
          saved={saved?.amount}
          parse={parseAmountInput}
          onSave={(amount) => setHolding(symbol, { amount })}
          error="Enter a number of rupees"
          placeholder="Optional"
        />
        <NumberField
          id={`buy-${symbol}`}
          label="Average buy price (₹)"
          saved={saved?.buyPrice}
          parse={parsePriceInput}
          onSave={(buyPrice) => setHolding(symbol, { buyPrice })}
          error="Enter a price above 0"
          placeholder="Optional"
        />
      </div>
      {mine && (
        <p className="mt-2 text-xs leading-5 text-ink-faint" data-testid={`holding-hint-${symbol}`}>
          {mine.value !== null && mine.pnl !== null && mine.pnlPct !== null ? (
            <>
              Worth {formatInr(mine.value)} now ·{" "}
              <span className={`font-medium ${tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : ""}`}>
                {tone === "flat" ? "no profit or loss" : arrowInrPct(mine.pnl, mine.pnlPct)}
              </span>
            </>
          ) : saved?.buyPrice !== undefined ? (
            "No price yet for this company, so no profit or loss."
          ) : (
            "Add a buy price to see profit or loss. Without it, FINN shows only today's move."
          )}
        </p>
      )}
      {!mine && saved?.buyPrice !== undefined && <p className="mt-2 text-xs leading-5 text-ink-faint">Add the amount invested to use this buy price.</p>}
    </div>
  );
}

/** The companies being researched, not held: "Watching". */
function Watching() {
  const index = useJson<ResearchIndex>("/data/research/index.json");
  if (index.kind !== "ready" || index.data.companies.length === 0) return null;
  return (
    <>
      <h3 className="mt-7 text-sm font-semibold">Watching</h3>
      <p className="mt-0.5 text-xs text-ink-faint">Companies you are researching, from the Interested tab.</p>
      <Card>
        {index.data.companies.map((c) => (
          <Link key={c.symbol} href={`/research?symbol=${encodeURIComponent(c.symbol)}`} className="flex min-h-14 items-center justify-between gap-3 px-4 py-2">
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{shortName(c.name)}</span>
              <span className="block text-xs text-ink-faint">{c.symbol}</span>
            </span>
            <span aria-hidden="true" className="text-ink-faint">
              ›
            </span>
          </Link>
        ))}
      </Card>
    </>
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
  const holdings = useInvested();
  const [confirmSample, setConfirmSample] = useState(false);

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
  const total = totalInvested(holdings, companies.map((c) => c.symbol));
  const sampleOn = hasSample(holdings);
  const sessionsBySymbol = new Map(brief.signals.map((s) => [s.symbol, s.sessions]));
  const samples = sampleHoldings(
    companies.map((c) => ({ symbol: c.symbol, close: priceView(sessionsBySymbol.get(c.symbol), brief.generated_at)?.close ?? null })),
  );

  return (
    <div>
      <Profile />

      <Section
        id="muted"
        title="My portfolio"
        count={`${companies.length} companies${muted.size > 0 ? ` · ${muted.size} muted` : ""}`}
        hint="The companies FINN watches for you. Switch one off to leave it out of the Brief and of Alerts."
      >
        <h3 className="mt-4 text-sm font-semibold">Show in my brief</h3>
        <Card>
          {companies.map((c) => (
            <SwitchRow
              key={c.symbol}
              label={c.name}
              ariaLabel={c.name}
              hint={`${c.symbol} · ${c.sector}`}
              checked={!muted.has(c.symbol)}
              dim={muted.has(c.symbol)}
              tag={muted.has(c.symbol) ? "Muted" : undefined}
              onChange={(on) => setMuted(c.symbol, !on)}
            />
          ))}
        </Card>
      </Section>

      <Section
        id="investments"
        title="My investments"
        count={total > 0 ? `Total invested ${formatInr(total)}` : undefined}
        hint="Optional. What you put into each company and, if you know it, the average price you paid. Kept on this phone only. With a buy price FINN shows profit and loss; without one, only today's move. For understanding only, not advice."
      >
        <div className="mt-3 rounded-2xl border border-line bg-surface p-3">
          {sampleOn && (
            <p className="mb-2 flex flex-wrap items-center gap-2 text-xs leading-5 text-ink-soft">
              <span className="rounded bg-backdrop px-1.5 py-0.5 font-medium">Sample holdings</span>
              Made-up numbers, not yours. Type over one to use your own.
            </p>
          )}
          {confirmSample ? (
            <div role="alertdialog" aria-label="Replace your entries with sample holdings?" className="space-y-2">
              <p className="text-sm font-medium">Replace what you entered with sample holdings?</p>
              <p className="text-xs leading-5 text-ink-soft">Your own amounts and buy prices will be removed. This cannot be undone.</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    applySample(samples);
                    setConfirmSample(false);
                  }}
                  className="min-h-11 flex-1 rounded-full bg-accent-bg text-sm font-medium text-on-accent"
                >
                  Replace with sample
                </button>
                <button type="button" onClick={() => setConfirmSample(false)} className="min-h-11 flex-1 rounded-full border border-line text-sm font-medium">
                  Keep mine
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => (hasOwnEntries(holdings) ? setConfirmSample(true) : applySample(samples))}
                disabled={Object.keys(samples).length === 0}
                className="min-h-11 flex-1 rounded-full border border-accent text-sm font-medium text-accent disabled:opacity-50"
              >
                Try with sample holdings
              </button>
              {sampleOn && (
                <button type="button" onClick={clearSample} className="min-h-11 flex-1 rounded-full border border-line text-sm font-medium">
                  Clear sample
                </button>
              )}
            </div>
          )}
        </div>
        <Card>
          {companies.map((c) => {
            const view = priceView(sessionsBySymbol.get(c.symbol), brief.generated_at);
            return (
              <HoldingRow
                key={c.symbol}
                symbol={c.symbol}
                name={shortName(c.name)}
                saved={holdings[c.symbol]}
                close={view?.close ?? null}
                prevClose={view?.prevClose ?? null}
                changePct={view?.changePct ?? 0}
              />
            );
          })}
        </Card>
        <Watching />
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
