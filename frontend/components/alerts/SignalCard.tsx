"use client";

import { useId, useState } from "react";
import { Chevron } from "@/components/brief/Chevron";
import { TONE, toneBox } from "@/components/brief/tone";
import { moveWords, type SignalAlert } from "@/lib/alerts";
import { CategoryIcon } from "@/components/ui/Icons";
import { Avatar, PriceChip } from "@/components/ui/Price";
import { formatDay, formatMove, formatPrice, formatShares } from "@/lib/format";

/** An unusual end-of-day move: price, volume, or both, measured against the user's own lines. */
export function SignalCard({ alert, reasons, note }: { alert: SignalAlert; reasons: string[]; note: string }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const tone = TONE[alert.tone];
  const s = alert.session;
  const price = alert.reasons.includes("price");
  const volume = alert.reasons.includes("volume");
  const ratio = s.volume_ratio ?? 0;

  const headline =
    price && volume
      ? `${alert.symbol} ${moveWords(s.change_pct)} on heavy volume`
      : price
        ? `${alert.symbol} ${moveWords(s.change_pct)}`
        : `${alert.symbol} traded ${ratio.toFixed(1)}× its usual volume`;

  return (
    <article className={`rounded-2xl border border-line ${toneBox(alert.tone, "bg-surface")}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="block min-h-11 w-full px-4 py-3 text-left"
      >
        <span className="flex items-start justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2.5">
            <Avatar symbol={alert.symbol} name={alert.name} size={34} />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-ink-soft">{alert.symbol}</span>
              <span className="flex items-center gap-1 text-xs text-ink-faint">
                <CategoryIcon category="results" size={14} />
                <span>End-of-day move</span>
              </span>
            </span>
          </span>
          <PriceChip sessions={alert.sessions} />
        </span>
        <span className="mt-2 flex items-center gap-2 text-xs text-ink-faint">
          <span className={`rounded px-1.5 py-0.5 font-medium ${tone.chipOnTint}`}>{tone.tag}</span>
          <time dateTime={s.day}>{formatDay(s.day)}</time>
        </span>
        <span className="mt-1 block text-base font-semibold leading-snug">{headline}</span>
        <span className="mt-1 block text-sm text-ink-soft">
          <span className={`font-medium ${tone.text}`}>{formatMove(s.change_pct)}</span> to {formatPrice(s.close)}
          {volume && <span> · {ratio.toFixed(1)}× average volume</span>}
        </span>
        <span className="mt-1.5 block text-xs leading-5 text-ink-soft">
          {reasons.map((reason) => (
            <span key={reason} className="block">
              {reason}
            </span>
          ))}
          <span className="block text-ink-faint">{note}</span>
        </span>
        <span className="mt-2 flex items-center gap-1 text-xs font-medium text-ink-faint">
          {open ? "Hide the numbers" : "The numbers"}
          <Chevron open={open} />
        </span>
      </button>

      {open && (
        <div id={panelId} className="border-t border-line px-4 py-3">
          <p className="text-xs text-ink-faint">{alert.name}</p>
          {s.avg_volume !== null && (
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              {formatShares(s.volume)} shares traded against a 20-day average of {formatShares(s.avg_volume)}.
            </p>
          )}
          <table className="mt-3 w-full text-left text-xs tabular-nums">
            <caption className="sr-only">Recent sessions for {alert.symbol}</caption>
            <thead className="text-ink-faint">
              <tr>
                <th scope="col" className="py-1 font-medium">Day</th>
                <th scope="col" className="py-1 text-right font-medium">Close</th>
                <th scope="col" className="py-1 text-right font-medium">Move</th>
                <th scope="col" className="py-1 text-right font-medium">Volume</th>
              </tr>
            </thead>
            <tbody>
              {[...alert.sessions].slice(-5).reverse().map((row) => (
                <tr key={row.day} className={row.day === s.day ? "font-semibold text-ink" : "text-ink-soft"}>
                  <th scope="row" className="py-1 font-[inherit]">{formatDay(row.day)}</th>
                  <td className="py-1 text-right">{formatPrice(row.close)}</td>
                  <td className="py-1 text-right">{formatMove(row.change_pct)}</td>
                  <td className="py-1 text-right">{row.volume_ratio === null ? "n/a" : `${row.volume_ratio.toFixed(1)}×`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}
