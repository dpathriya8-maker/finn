"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { CompanyResearch } from "@/components/research/CompanyResearch";
import { isValidTicker, normaliseTicker, type ResearchIndex } from "@/lib/research";
import { useJson } from "@/lib/useJson";

const STATUS_NOTE = { ready: "Promises judged", statements_only: "Documents read", no_documents: "No documents" } as const;

/** The Research tab: a ticker box and the companies researched in advance; with ?symbol=, one company's research. */
export function ResearchScreen() {
  const params = useSearchParams();
  const symbol = normaliseTicker(params.get("symbol") ?? "");
  if (symbol) {
    return isValidTicker(symbol) ? (
      <CompanyResearch key={symbol} symbol={symbol} />
    ) : (
      <section className="rounded-2xl border border-line p-5" role="alert">
        <h2 className="text-base font-medium text-watch">That is not an NSE ticker</h2>
        <p className="mt-1 text-sm leading-6 text-ink-soft">A ticker is up to 20 capital letters, digits, &amp; or -, such as RELIANCE or M&amp;M.</p>
        <Link href="/research" className="mt-3 inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-2">
          Try another
        </Link>
      </section>
    );
  }
  return <Home />;
}

function Home() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [touched, setTouched] = useState(false);
  const index = useJson<ResearchIndex>("/data/research/index.json");
  const symbol = normaliseTicker(text);
  const invalid = touched && !isValidTicker(symbol);

  return (
    <div className="space-y-6">
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          setTouched(true);
          if (isValidTicker(symbol)) router.push(`/research?symbol=${encodeURIComponent(symbol)}`);
        }}
      >
        <label htmlFor="ticker" className="text-sm font-medium">
          NSE ticker
        </label>
        <input
          id="ticker"
          name="ticker"
          value={text}
          onChange={(event) => setText(event.target.value)}
          autoCapitalize="characters"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          inputMode="text"
          maxLength={24}
          placeholder="For example RELIANCE or M&M"
          aria-invalid={invalid}
          aria-describedby={invalid ? "ticker-error" : "ticker-help"}
          className="mt-1.5 min-h-12 w-full rounded-xl border border-line bg-surface px-4 text-base uppercase placeholder:normal-case placeholder:text-ink-faint"
        />
        {invalid ? (
          <p id="ticker-error" role="alert" className="mt-1.5 text-sm text-watch">
            Enter an NSE ticker: up to 20 capital letters, digits, &amp; or -.
          </p>
        ) : (
          <p id="ticker-help" className="mt-1.5 text-xs leading-5 text-ink-faint">
            Any company on the NSE. One that is not listed below is read on demand, which can take a minute or two.
          </p>
        )}
        <button type="submit" className="mt-3 min-h-12 w-full rounded-full bg-ink text-base font-semibold text-surface">
          Research this company
        </button>
      </form>

      <section aria-labelledby="ready-title">
        <h2 id="ready-title" className="text-sm font-semibold">
          Ready to read
        </h2>
        {index.kind === "loading" && <div className="mt-2 h-24 animate-pulse rounded-2xl bg-line" aria-label="Loading the list" />}
        {index.kind === "error" && <p className="mt-2 text-sm text-ink-soft">The list could not be loaded. Type a ticker above.</p>}
        {index.kind === "ready" && (
          <ul className="mt-2 divide-y divide-line rounded-2xl border border-line">
            {index.data.companies.map((company) => (
              <li key={company.symbol}>
                <Link href={`/research?symbol=${encodeURIComponent(company.symbol)}`} className="flex min-h-14 items-center justify-between gap-3 px-4 py-2">
                  <span>
                    <span className="block text-sm font-semibold">{company.name}</span>
                    <span className="block text-xs text-ink-faint">
                      {company.symbol} · {company.documents} documents · {STATUS_NOTE[company.status]}
                    </span>
                  </span>
                  <span aria-hidden="true" className="text-ink-faint">
                    ›
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs leading-5 text-ink-faint">
        Every claim shown here comes from a filing the company itself made: earnings-call transcripts and the annual report. No news, no broker notes, no outside knowledge.
      </p>
    </div>
  );
}
