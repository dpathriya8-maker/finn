"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RecordView } from "@/components/research/RecordView";
import { runResearchFlow, type ResearchState } from "@/lib/research";
import { realDeps } from "@/lib/researchApi";

function Panel({ title, tone = "text-ink", children, role }: { title: string; tone?: string; children: React.ReactNode; role?: "status" | "alert" }) {
  return (
    <section className="rounded-2xl border border-line p-5" role={role} aria-live={role === "status" ? "polite" : undefined}>
      <h2 className={`text-base font-medium ${tone}`}>{title}</h2>
      <div className="mt-1 space-y-2 text-sm leading-6 text-ink-soft">{children}</div>
    </section>
  );
}

function BackLink() {
  return (
    <Link href="/research" className="inline-flex min-h-11 items-center text-sm font-medium text-ink-soft underline underline-offset-2">
      ← All companies
    </Link>
  );
}

/** One company's research, and every honest state on the way to it (checking, engine waking, working, failed). */
export function CompanyResearch({ symbol }: { symbol: string }) {
  const [state, setState] = useState<ResearchState>({ kind: "checking" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // The flow reports "checking" itself as its first step, and stops when the company changes or the screen closes.
    return runResearchFlow(symbol, realDeps, setState);
  }, [symbol, attempt]);

  const retry = (
    <button type="button" onClick={() => setAttempt((n) => n + 1)} className="mt-2 inline-flex min-h-11 items-center rounded-full border border-line px-4 text-sm font-medium">
      Try again
    </button>
  );

  return (
    <div className="space-y-4">
      <BackLink />
      {state.kind === "checking" && <div className="h-40 animate-pulse rounded-2xl bg-line" aria-label={`Looking for research on ${symbol}`} />}
      {state.kind === "waking" && (
        <Panel title="Waking up the research engine" tone="text-watch" role="status">
          <p>The engine sleeps when nobody has used it for a while. Waking it takes about a minute. Waited {state.seconds} seconds so far.</p>
          <p>Companies listed on the Research tab are ready without it.</p>
        </Panel>
      )}
      {state.kind === "running" && (
        <Panel title={`Reading ${symbol}’s filings`} role="status">
          <p>{state.stage}…</p>
          <p>This company was not researched in advance, so the engine is finding its transcripts and annual report and reading them. It usually takes one to three minutes. {state.seconds > 0 ? `${state.seconds} seconds so far.` : ""}</p>
        </Panel>
      )}
      {state.kind === "failed" && (
        <Panel title="This research could not be completed" tone="text-watch" role="alert">
          <p>{state.reason}</p>
          {retry}
        </Panel>
      )}
      {state.kind === "capped" && (
        <Panel title="Today’s allowance of new research is used" tone="text-watch" role="alert">
          <p>{state.detail}</p>
        </Panel>
      )}
      {state.kind === "offline" && (
        <Panel title="The research engine is not reachable" tone="text-bad" role="alert">
          <p>It did not wake within a minute and a half. Companies listed on the Research tab can still be read.</p>
          {retry}
        </Panel>
      )}
      {state.kind === "unconfigured" && (
        <Panel title={`${symbol} has not been researched yet`}>
          <p>Only companies researched in advance are available in this version, and the live engine is not connected here.</p>
        </Panel>
      )}
      {state.kind === "ready" && <RecordView record={state.record} source={state.source} />}
    </div>
  );
}
