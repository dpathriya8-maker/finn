/** Research on a company, from its own filings. Types mirror backend/app/pull/research.py; the logic here is
 * ordering, wording, links and the fetch-and-poll flow that turns "I typed a ticker" into a record or an honest reason. */

export type ResearchDocument = {
  id: string;
  kind: "transcript" | "annual_report";
  title: string;
  period: string | null;
  date: string;
  url: string;
  pages: number;
  bytes: number;
  sha256: string;
};

export type Evidence = { doc: string; page: number; quote: string };

export type PromiseStatus = "Kept" | "Partly" | "Missed" | "Not followed up" | "Too early";

/** The promised and the reported number, present only when both were found in the quotes; the share is computed by the engine. */
export type VerdictNumbers = { target: number; actual: number; unit: string; lower_is_better: boolean; attainment_pct: number };

export type TrackedPromise = {
  id: string;
  doc: string;
  quarter: string;
  page: number;
  quote: string;
  what: string;
  by_when: string | null;
  kind: string;
  /** When it is due, as management said it ("Q3 FY27"), and the last day of that period as the engine read it. Absent in older records. */
  target_period?: string | null;
  due?: string | null;
  verdict: { status: PromiseStatus; reason: string; downgraded: boolean; delayed?: boolean; numbers?: VerdictNumbers | null; evidence: Evidence[] };
};

export type Scorecard = {
  kept: number;
  partly: number;
  missed: number;
  /** Absent in records made before the verdict existed. */
  not_followed_up?: number;
  too_early: number;
  total: number;
  decided: number;
  delivery_rate_pct: number | null;
  /** Commitments with no stated time frame, which cannot be checked and are not tracked. */
  no_deadline?: number;
  /** The latest call on record (its date and quarter): "too early" is measured against it. */
  as_of?: string;
  as_of_call?: string;
};

export type Statement = { doc: string; quarter: string | null; page: number; text: string };

export type ResearchRecord = {
  schema: number;
  symbol: string;
  name: string;
  generated_at: string;
  /** ready: promises judged by a model. statements_only: documents read, no model ran. no_documents: nothing to read. */
  status: "ready" | "statements_only" | "no_documents";
  reason: string | null;
  model: { ran: boolean; reason: string | null; calls?: number; cache_hits?: number; models?: string[] };
  documents: ResearchDocument[];
  warnings: string[];
  promises: TrackedPromise[];
  scorecard: Scorecard | null;
  statements: Statement[];
};

export type AskResult = {
  question: string;
  status: "answered" | "passages" | "not_found";
  answer: string | null;
  citations: Evidence[];
  passages: { doc: string; page: number; text: string }[];
  note: string;
  documents: { id: string; title: string; period: string | null; url: string }[];
};

// ------------------------------------------------------------------------------------------------ small rules
const TICKER = /^[A-Z0-9&-]{1,20}$/;

/** What was typed, as an NSE symbol: trimmed, upper-cased, spaces removed. */
export function normaliseTicker(input: string): string {
  return input.trim().toUpperCase().replace(/\s+/g, "");
}

export function isValidTicker(symbol: string): boolean {
  return TICKER.test(symbol);
}

/** Bad news first (design rule 4): what was missed, what went quiet, what was partly kept, then kept, then not yet due. */
export const STATUS_ORDER: PromiseStatus[] = ["Missed", "Not followed up", "Partly", "Kept", "Too early"];

export const STATUS_LOOK: Record<PromiseStatus, { tone: "bad" | "watch" | "good" | "neutral"; meaning: string }> = {
  Missed: { tone: "bad", meaning: "Its date has passed and later calls show it did not happen, or management has pushed it back or dropped it" },
  "Not followed up": { tone: "watch", meaning: "Its date has passed and no later call mentions it" },
  Partly: { tone: "watch", meaning: "Delivered in part, or 75 to 99% of the number promised" },
  Kept: { tone: "good", meaning: "Its date has passed and later calls show it was delivered" },
  "Too early": { tone: "neutral", meaning: "Its date has not come yet, as of the latest call" },
};

/** The status as shown: a promise management itself pushed back reads "Missed — delayed". */
export function statusLabel(verdict: Pick<TrackedPromise["verdict"], "status" | "delayed">): string {
  return verdict.status === "Missed" && verdict.delayed ? "Missed — delayed" : verdict.status;
}

/** "Promised 10 lakh, reported 9 lakh: 90% of the promise", from the numbers the engine checked against the quotes. */
export function numbersText(n: VerdictNumbers): string {
  const show = (v: number) => (n.unit === "%" ? `${v}%` : n.unit ? `${v} ${n.unit}` : `${v}`);
  return `Promised ${show(n.target)}, reported ${show(n.actual)}: ${n.attainment_pct}% of the promise`;
}

/** When it is due: the date the engine worked out from the speaker's own words, with those words; older records had only the words. */
export function dueText(p: Pick<TrackedPromise, "due" | "by_when" | "target_period">): string | null {
  if (p.due) return p.by_when ? `${dateLabel(p.due)} (“${p.by_when}”)` : dateLabel(p.due);
  return p.by_when || p.target_period || null;
}

export function orderPromises(promises: readonly TrackedPromise[]): TrackedPromise[] {
  const rank = (p: TrackedPromise) => STATUS_ORDER.indexOf(p.verdict.status);
  return [...promises].sort((a, b) => rank(a) - rank(b) || a.doc.localeCompare(b.doc) || a.page - b.page);
}

/** "Delivered 63% of the promises that could be judged", or why there is no rate. */
export function deliveryText(card: Scorecard): string {
  if (card.delivery_rate_pct === null) {
    return card.decided === 0 ? "No promise could be judged yet" : `Only ${card.decided} promise${card.decided === 1 ? "" : "s"} could be judged, too few for a rate`;
  }
  return `Delivered ${card.delivery_rate_pct}% of the promises that could be judged`;
}

/** A link that opens the PDF at the page, in browsers that honour the #page= parameter. */
export function pageLink(doc: Pick<ResearchDocument, "url"> | undefined, page: number): string | null {
  return doc ? `${doc.url}#page=${page}` : null;
}

export function sourceLabel(doc: ResearchDocument | undefined, page: number): string {
  if (!doc) return `page ${page}`;
  return `${doc.kind === "annual_report" ? "Annual report" : `${doc.period ?? "Earnings"} call`}, page ${page}`;
}

export function byId(documents: readonly ResearchDocument[]): Map<string, ResearchDocument> {
  return new Map(documents.map((d) => [d.id, d]));
}

export function fileSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

// ------------------------------------------------------------------------------------------------ the flow
export type ResearchState =
  | { kind: "checking" }
  | { kind: "waking"; seconds: number }
  | { kind: "running"; stage: string; seconds: number }
  | { kind: "ready"; record: ResearchRecord; source: "shipped" | "live" }
  | { kind: "failed"; reason: string }
  | { kind: "capped"; detail: string }
  | { kind: "offline" }
  | { kind: "unconfigured" };

type BackendReply =
  | { state: "ready"; record: ResearchRecord }
  | { state: "running"; stage: string; seconds: number }
  | { state: "failed"; reason: string }
  | { state: "none" }
  | { state: "capped"; detail: string };

export type FlowDeps = {
  /** The record shipped with the app, or null if there is none. */
  shipped: (symbol: string) => Promise<ResearchRecord | null>;
  /** The engine's answer, or throws if the engine cannot be reached. */
  read: (symbol: string) => Promise<BackendReply>;
  start: (symbol: string) => Promise<BackendReply>;
  sleep: (ms: number) => Promise<void>;
  now: () => number;
  configured: boolean;
};

export const POLL_MS = 3_000;
export const WAKE_RETRY_MS = 5_000;
export const WAKE_GIVE_UP_MS = 90_000;
export const JOB_GIVE_UP_MS = 6 * 60_000;

/**
 * Get a company's research: the record shipped with the app if there is one (instant, no engine needed); otherwise ask
 * the engine, which may be asleep (a free instance takes about a minute to wake, shown as "waking") and may have to do
 * the work (shown as "running" with its stage). Every way it can end is a state the screen can word honestly.
 * Returns a function that stops the flow.
 */
export function runResearchFlow(symbol: string, deps: FlowDeps, emit: (s: ResearchState) => void): () => void {
  let stopped = false;
  const say = (s: ResearchState) => {
    if (!stopped) emit(s);
  };

  (async () => {
    say({ kind: "checking" });
    try {
      const shipped = await deps.shipped(symbol);
      if (shipped) return say({ kind: "ready", record: shipped, source: "shipped" });
    } catch {
      /* no shipped record: carry on to the engine */
    }
    if (!deps.configured) return say({ kind: "unconfigured" });

    const began = deps.now();
    let started = false;
    while (!stopped) {
      let reply: BackendReply;
      try {
        reply = await deps.read(symbol);
      } catch {
        const waited = deps.now() - began;
        if (waited > WAKE_GIVE_UP_MS) return say({ kind: "offline" });
        say({ kind: "waking", seconds: Math.round(waited / 1000) });
        await deps.sleep(WAKE_RETRY_MS);
        continue;
      }
      if (reply.state === "none" && !started) {
        started = true;
        try {
          reply = await deps.start(symbol);
        } catch {
          return say({ kind: "offline" });
        }
      }
      switch (reply.state) {
        case "ready":
          return say({ kind: "ready", record: reply.record, source: "live" });
        case "failed":
          return say({ kind: "failed", reason: reply.reason });
        case "capped":
          return say({ kind: "capped", detail: reply.detail });
        case "running":
          say({ kind: "running", stage: reply.stage, seconds: reply.seconds });
          break;
        case "none":
          say({ kind: "running", stage: "Starting", seconds: 0 });
          break;
      }
      if (deps.now() - began > JOB_GIVE_UP_MS) return say({ kind: "failed", reason: "The research is taking much longer than usual. Try again in a few minutes." });
      await deps.sleep(POLL_MS);
    }
  })();

  return () => {
    stopped = true;
  };
}

const DATE = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" });

/** "8 Aug 2026" for a YYYY-MM-DD or ISO timestamp; the text itself if it is not a date. */
export function dateLabel(iso: string): string {
  const date = new Date(iso.length === 10 ? `${iso}T12:00:00+05:30` : iso);
  return Number.isNaN(date.getTime()) ? iso : DATE.format(date);
}

export type IndexEntry = { symbol: string; name: string; status: ResearchRecord["status"]; documents: number; generated_at: string };
export type ResearchIndex = { schema: number; generated_at: string; companies: IndexEntry[] };

/** Quarter by quarter, newest first, for the statements list. */
export function statementsByCall(statements: readonly Statement[]): { quarter: string; doc: string; items: Statement[] }[] {
  const groups = new Map<string, { quarter: string; doc: string; items: Statement[] }>();
  for (const s of statements) {
    const group = groups.get(s.doc) ?? { quarter: s.quarter ?? "Earnings call", doc: s.doc, items: [] };
    group.items.push(s);
    groups.set(s.doc, group);
  }
  return [...groups.values()].sort((a, b) => b.doc.localeCompare(a.doc, undefined, { numeric: true }));
}
