"use client";

import { useId, useState } from "react";
import { formatInr, parseAmountInput, useInvested } from "@/lib/invested";
import { closeCaption, priceView } from "@/lib/prices";
import type { Session } from "@/lib/types";
import {
  ariaValueText,
  changeRow,
  CHIPS,
  DEFAULT_AMOUNT,
  periodChange,
  scenario,
  signedInr,
  signedPct,
  SLIDER_MAX,
  SLIDER_MIN,
  type Tone,
  type WhatIfRow,
} from "@/lib/whatif";

const TONE_TEXT: Record<Tone, string> = { good: "text-good", bad: "text-bad", flat: "text-ink-soft" };

function Row({ row }: { row: WhatIfRow }) {
  return (
    <li className="flex min-w-0 items-baseline justify-between gap-3 py-1.5">
      <span className="min-w-0 text-sm text-ink-soft">{row.label}</span>
      <span className={`shrink-0 text-base font-semibold tabular-nums ${TONE_TEXT[row.tone]}`}>{row.text}</span>
    </li>
  );
}

/**
 * "What if": what a company's real moves mean in rupees, for people who feel rupees and not percentages. An amount (the one from
 * My investments if there is one, else ₹10,000), then what today's move and the last 30 days did to it, then a slider and chips for
 * "if it moves ...". Every number is the amount times a real close-to-close move, worked out in `lib/whatif.ts`. It predicts nothing
 * and gives no advice, and says so. The same component sits in an open Brief card and at the top of a Research page.
 */
export function WhatIf({ symbol, sessions, generatedAt }: { symbol: string; sessions: readonly Session[] | undefined | null; generatedAt: string | undefined }) {
  const saved = useInvested()[symbol];
  const [draft, setDraft] = useState<string | null>(null); // what is typed; null until the reader edits
  const [editing, setEditing] = useState(false);
  const [pct, setPct] = useState(0);
  const amountId = useId();
  const rangeId = useId();

  const view = priceView(sessions, generatedAt);
  if (!view) return null; // no real price, no calculator: nothing is invented

  const text = draft ?? String(saved ?? DEFAULT_AMOUNT);
  const parsed = parseAmountInput(text);
  const amount = parsed.valid ? parsed.value : null; // null: empty or not a number
  const month = periodChange(sessions, generatedAt);
  const shown = editing || !parsed.valid || parsed.value === null ? text : formatInr(parsed.value);
  const result = amount === null ? null : scenario(amount, pct);

  return (
    <section aria-label="What if" className="min-w-0 rounded-2xl border border-line bg-surface p-3.5">
      <h3 className="text-sm font-semibold">What if</h3>
      <p className="mt-0.5 text-xs text-ink-faint">What these moves mean in rupees.</p>

      <div className="mt-3 flex items-center justify-between gap-3">
        <label htmlFor={amountId} className="text-sm font-medium">
          Amount (₹)
        </label>
        <input
          id={amountId}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={shown}
          aria-invalid={!parsed.valid}
          aria-describedby={parsed.valid ? undefined : `${amountId}-error`}
          onFocus={() => {
            setEditing(true);
            if (draft === null) setDraft(String(saved ?? DEFAULT_AMOUNT));
          }}
          onBlur={() => setEditing(false)}
          onChange={(event) => setDraft(event.target.value)}
          className={`min-h-11 w-40 min-w-0 rounded-xl border bg-page px-3 text-right text-base tabular-nums ${parsed.valid ? "border-line" : "border-bad"}`}
        />
      </div>
      {!parsed.valid && (
        <p id={`${amountId}-error`} role="alert" className="mt-1 text-right text-xs text-bad">
          Enter a number of rupees, 0 or more
        </p>
      )}

      {amount === null ? (
        <p className="mt-3 text-sm text-ink-soft" role="status">
          {parsed.valid ? "Enter an amount to see what it means in rupees." : "Fix the amount to see what it means in rupees."}
        </p>
      ) : (
        <>
          <ul className="mt-2 divide-y divide-line">
            <Row row={changeRow("Today", view.changePct, amount, 2)} />
            {month && <Row row={changeRow("Last 30 days", month.pct, amount, 1)} />}
          </ul>

          <div className="mt-3">
            <label htmlFor={rangeId} className="text-sm font-medium">
              If it moves
            </label>
            <input
              id={rangeId}
              type="range"
              min={SLIDER_MIN}
              max={SLIDER_MAX}
              step={1}
              value={pct}
              aria-valuetext={ariaValueText(amount, pct)}
              onChange={(event) => setPct(Number(event.target.value))}
              className="mt-1 h-11 w-full accent-[var(--accent)]"
            />
            <div className="flex justify-between text-xs tabular-nums text-ink-faint" aria-hidden="true">
              <span>{signedPct(SLIDER_MIN)}</span>
              <span>0%</span>
              <span>{signedPct(SLIDER_MAX)}</span>
            </div>
            <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Quick moves">
              {CHIPS.map((chip) => (
                <li key={chip}>
                  <button
                    type="button"
                    aria-pressed={pct === chip}
                    onClick={() => setPct(chip)}
                    className={`min-h-11 min-w-12 rounded-full border px-2 text-sm font-medium tabular-nums ${pct === chip ? "border-accent bg-backdrop text-accent" : "border-line text-ink-soft"}`}
                  >
                    {signedPct(chip)}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {result && (
            <p role="status" aria-live="polite" className="mt-3 break-words text-sm leading-6">
              {pct === 0 ? "If it does not move" : `If it moves ${signedPct(pct)}`}: you&apos;d have <span className="font-semibold tabular-nums">{formatInr(result.total)}</span>{" "}
              <span className="whitespace-nowrap">
                (
                <span className={`font-semibold tabular-nums ${TONE_TEXT[result.tone]}`}>
                  {result.change > 0 ? "▲ " : result.change < 0 ? "▼ " : ""}
                  {signedInr(result.change)}
                </span>
                )
              </span>
            </p>
          )}
        </>
      )}

      <p className="mt-3 text-xs leading-5 text-ink-faint">Based on {closeCaption(view.day)}. For understanding only, not advice.</p>
    </section>
  );
}
