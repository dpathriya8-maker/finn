import { basisLabel, checkView, DELTA_CLASS, marginLines, metricRows, pagesLabel, printedLine, unitNote } from "@/lib/results";
import { MetricBars } from "@/components/ui/Charts";
import type { ResultsCard } from "@/lib/types";

const CHECK_TONE = { good: "bg-good-bg text-good", watch: "bg-watch-bg text-watch", neutral: "bg-backdrop text-ink-soft" } as const;

/** The figures behind a results filing: Revenue, EBITDA, PBT and PAT against last quarter and last year. */
export function ResultsCardView({ card }: { card: ResultsCard }) {
  if (card.status === "failed") {
    return (
      <div role="note" className="rounded-xl border border-line bg-backdrop px-3 py-2.5 text-sm leading-6 text-ink-soft">
        <p className="font-medium text-ink">Figures not shown</p>
        <p>{card.reason}</p>
      </div>
    );
  }

  const rows = metricRows(card);
  const check = checkView(card.check);
  const margins = marginLines(card);
  const computed = rows.filter((row) => row.derived);
  const conversion = unitNote(card.unit_printed);
  const pages = pagesLabel(card.source.pages);

  return (
    <section aria-label={`${card.period.label} results figures`} className="text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="font-semibold">{card.period.label}</h3>
        <p className="text-xs text-ink-faint">
          {basisLabel(card.basis)} · ₹ crore
        </p>
      </div>

      <table className="mt-2 w-full table-fixed tabular-nums">
        <caption className="sr-only">
          {card.period.label} figures in rupees crore, with the change from the previous quarter and from a year earlier
        </caption>
        <thead>
          <tr className="text-xs text-ink-faint">
            <th scope="col" className="w-[30%] pb-1 text-left font-medium">
              <span className="sr-only">Measure</span>
            </th>
            <th scope="col" className="w-[24%] pb-1 text-right font-medium">
              This qtr
            </th>
            <th scope="col" className="w-[23%] pb-1 text-right font-medium">
              QoQ
            </th>
            <th scope="col" className="w-[23%] pb-1 text-right font-medium">
              YoY
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-t border-line">
              <th scope="row" className="py-2 pr-1 text-left font-medium">
                {row.full ? (
                  <abbr title={row.full} className="no-underline">
                    {row.text}
                  </abbr>
                ) : (
                  row.text
                )}
                {row.derived && <span aria-label="computed here"> †</span>}
              </th>
              <td className="py-2 text-right font-semibold">{row.current}</td>
              <td className={`py-2 text-right ${DELTA_CLASS[row.qoq.direction]}`}>{row.qoq.text}</td>
              <td className={`py-2 text-right ${DELTA_CLASS[row.yoy.direction]}`}>{row.yoy.text}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <MetricBars card={card} />

      {margins.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs leading-5 text-ink-soft">
          {margins.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      {computed.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs leading-5 text-ink-faint">
          {computed.map((row) => (
            <li key={row.key}>
              † <span className="font-medium text-ink-soft">{row.text}:</span> {row.derived}
            </li>
          ))}
        </ul>
      )}

      {(card.verification || card.warnings.length > 0) && (
        <ul className="mt-2 space-y-1 rounded-xl bg-watch-bg px-3 py-2 text-xs leading-5 text-watch">
          {card.verification && <li>{card.verification}</li>}
          {card.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="mt-3 text-xs leading-5">
        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium ${CHECK_TONE[check.tone]}`}>
          <span aria-hidden="true">{check.icon}</span>
          {check.title}
        </span>
        {check.lines.map((line) => (
          <p key={line} className="mt-1 text-ink-faint">
            {line}
          </p>
        ))}
      </div>

      <details className="group mt-3 text-xs leading-5 text-ink-soft">
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-medium underline underline-offset-2">
          Figures as printed in the filing{pages ? ` (${pages})` : ""}
        </summary>
        <ul className="space-y-1.5 pb-1">
          <li className="text-ink-faint">Listed as: this quarter · previous quarter · the same quarter a year earlier.</li>
          {card.metrics.map((metric) => (
            <li key={metric.key} className="break-words">
              <span className="font-medium text-ink">{metric.key === "ebitda" ? "EBITDA" : metric.label}</span>
              <br />
              {printedLine(metric)}
            </li>
          ))}
          {conversion && <li className="text-ink-faint">{conversion}</li>}
          <li className="text-ink-faint">Changes and margins are calculated from these figures, not taken from the filing.</li>
        </ul>
      </details>
    </section>
  );
}
