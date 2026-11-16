/** The calls the Research screen makes: the record shipped with the app, and the engine's research and ask routes. */
import { API_URL } from "@/lib/api";
import type { AskResult, FlowDeps, ResearchRecord } from "@/lib/research";

const REQUEST_TIMEOUT_MS = 12_000;

async function request(url: string, init: RequestInit = {}): Promise<Response> {
  const life = new AbortController();
  const timer = setTimeout(() => life.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { cache: "no-store", ...init, signal: life.signal });
  } finally {
    clearTimeout(timer);
  }
}

type Reply = Awaited<ReturnType<FlowDeps["read"]>>;

async function toReply(res: Response): Promise<Reply> {
  if (res.status === 429) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    return { state: "capped", detail: body.detail ?? "Today's allowance of fresh research has been used." };
  }
  if (res.status === 404) return { state: "none" };
  if (!res.ok) throw new Error(`the engine answered ${res.status}`);
  return (await res.json()) as Reply; // 200 ready or failed, 202 running
}

let prepared: Promise<string[]> | null = null;

/** The companies researched in advance (the Research tab's list), asked once. */
function preparedSymbols(): Promise<string[]> {
  prepared ??= fetch("/data/research/index.json", { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : { companies: [] }))
    .then((data: { companies?: { symbol: string }[] }) => (data.companies ?? []).map((c) => c.symbol))
    .catch(() => []);
  return prepared;
}

export const realDeps: FlowDeps = {
  configured: Boolean(API_URL),
  now: () => Date.now(),
  sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  async shipped(symbol) {
    if (!(await preparedSymbols()).includes(symbol)) return null; // not prepared: go straight to the engine, with no failed request
    const res = await fetch(`/data/research/${encodeURIComponent(symbol)}.json`, { cache: "no-store" });
    return res.ok ? ((await res.json()) as ResearchRecord) : null;
  },
  async read(symbol) {
    return toReply(await request(`${API_URL}/research/${encodeURIComponent(symbol)}`));
  },
  async start(symbol) {
    return toReply(await request(`${API_URL}/research/${encodeURIComponent(symbol)}`, { method: "POST" }));
  },
};

export type AskOutcome =
  | { kind: "result"; result: AskResult }
  | { kind: "refused"; message: string } // the engine said no, in words fit to show
  | { kind: "unreachable" }; // the engine could not be reached (asleep, offline, or not configured)

/** Ask the documents. Only the engine can answer, so a sleeping engine is a state, not an error. */
export async function askDocuments(ticker: string, question: string): Promise<AskOutcome> {
  if (!API_URL) return { kind: "unreachable" };
  let res: Response;
  try {
    res = await request(`${API_URL}/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker, question }) });
  } catch {
    return { kind: "unreachable" };
  }
  if (res.ok) return { kind: "result", result: (await res.json()) as AskResult };
  if (res.status === 429) return { kind: "refused", message: "That is too many questions in a short time. Wait a minute and ask again." };
  const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
  const message = typeof body.detail === "string" ? body.detail : "The documents could not be searched just now. Try again in a moment.";
  return res.status >= 500 ? { kind: "unreachable" } : { kind: "refused", message };
}
