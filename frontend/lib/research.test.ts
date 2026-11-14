import { describe, expect, it } from "vitest";
import {
  byId,
  deliveryText,
  fileSize,
  isValidTicker,
  normaliseTicker,
  orderPromises,
  pageLink,
  runResearchFlow,
  sourceLabel,
  type FlowDeps,
  type ResearchDocument,
  type ResearchRecord,
  type ResearchState,
  type Scorecard,
  type TrackedPromise,
} from "@/lib/research";

const DOC: ResearchDocument = { id: "d1", kind: "transcript", title: "Q1 FY27 earnings call transcript", period: "Q1 FY27", date: "2026-08-08", url: "https://www.bseindia.com/x.pdf", pages: 20, bytes: 600_000, sha256: "a".repeat(64) };
const REPORT: ResearchDocument = { ...DOC, id: "d2", kind: "annual_report", title: "Annual report FY26", period: "FY26", bytes: 12 * 1024 * 1024 };

function promise(id: string, status: TrackedPromise["verdict"]["status"], doc = "d1", page = 3): TrackedPromise {
  return { id, doc, quarter: "Q1 FY27", page, quote: "q", what: "w", by_when: null, kind: "other", verdict: { status, reason: "", downgraded: false, evidence: [] } };
}

describe("tickers", () => {
  it("are tidied and validated the way the engine validates them", () => {
    expect(normaliseTicker("  bajaj finance ")).toBe("BAJAJFINANCE");
    expect(normaliseTicker("m&m")).toBe("M&M");
    for (const ok of ["HAL", "M&M", "BAJAJ-AUTO", "A", "X".repeat(20)]) expect(isValidTicker(ok)).toBe(true);
    for (const bad of ["", "hal", "H AL", "X".repeat(21), "<script>", "A.B", "HAL;DROP"]) expect(isValidTicker(bad)).toBe(false);
  });
});

describe("the promise list", () => {
  it("puts what was missed first, then partly, kept, and not yet due; within a status, by document and page", () => {
    const ordered = orderPromises([promise("a", "Kept"), promise("b", "Too early"), promise("c", "Missed", "d2", 9), promise("d", "Partly"), promise("e", "Missed", "d1", 4)]);
    expect(ordered.map((p) => p.id)).toEqual(["e", "c", "d", "a", "b"]);
  });
  it("does not change the list it is given", () => {
    const input = [promise("a", "Kept"), promise("b", "Missed")];
    orderPromises(input);
    expect(input.map((p) => p.id)).toEqual(["a", "b"]);
  });
});

describe("words and links", () => {
  it("says what the delivery rate is, or why there is none", () => {
    const card = (over: Partial<Scorecard>): Scorecard => ({ kept: 0, partly: 0, missed: 0, too_early: 0, total: 0, decided: 0, delivery_rate_pct: null, ...over });
    expect(deliveryText(card({ decided: 4, delivery_rate_pct: 63 }))).toBe("Delivered 63% of the promises that could be judged");
    expect(deliveryText(card({ decided: 2 }))).toBe("Only 2 promises could be judged, too few for a rate");
    expect(deliveryText(card({ decided: 1 }))).toBe("Only 1 promise could be judged, too few for a rate");
    expect(deliveryText(card({}))).toBe("No promise could be judged yet");
  });
  it("links to the page and names the source", () => {
    expect(pageLink(DOC, 7)).toBe("https://www.bseindia.com/x.pdf#page=7");
    expect(pageLink(undefined, 7)).toBeNull();
    expect(sourceLabel(DOC, 7)).toBe("Q1 FY27 call, page 7");
    expect(sourceLabel(REPORT, 112)).toBe("Annual report, page 112");
    expect(sourceLabel(undefined, 3)).toBe("page 3");
    expect(byId([DOC, REPORT]).get("d2")?.title).toBe("Annual report FY26");
  });
  it("sizes a file in KB or MB", () => {
    expect(fileSize(600_000)).toBe("586 KB");
    expect(fileSize(12 * 1024 * 1024)).toBe("12.0 MB");
    expect(fileSize(10)).toBe("1 KB");
  });
});

// ---------------------------------------------------------------------------------------------- the flow
const RECORD = { symbol: "ACME", name: "Acme Ltd", status: "statements_only", documents: [DOC] } as unknown as ResearchRecord;

/** A clock the fake sleep moves, so "ninety seconds" takes no time. */
function harness(overrides: Partial<FlowDeps>) {
  let clock = 0;
  const states: ResearchState[] = [];
  const calls: string[] = [];
  const deps: FlowDeps = {
    configured: true,
    now: () => clock,
    sleep: async (ms) => {
      clock += ms;
    },
    shipped: async () => null,
    read: async () => ({ state: "none" }),
    start: async () => ({ state: "running", stage: "Starting", seconds: 0 }),
    ...overrides,
  };
  const spied: FlowDeps = {
    ...deps,
    shipped: async (s) => (calls.push("shipped"), deps.shipped(s)),
    read: async (s) => (calls.push("read"), deps.read(s)),
    start: async (s) => (calls.push("start"), deps.start(s)),
  };
  const done = new Promise<void>((resolve) => {
    runResearchFlow("ACME", spied, (s) => {
      states.push(s);
      if (["ready", "failed", "capped", "offline", "unconfigured"].includes(s.kind)) resolve();
    });
  });
  return { states, calls, done };
}

describe("runResearchFlow", () => {
  it("shows a record shipped with the app at once and never wakes the engine", async () => {
    const h = harness({ shipped: async () => RECORD });
    await h.done;
    expect(h.states.map((s) => s.kind)).toEqual(["checking", "ready"]);
    expect(h.states[1]).toMatchObject({ kind: "ready", source: "shipped" });
    expect(h.calls).toEqual(["shipped"]);
  });

  it("says so when there is nothing shipped and no engine is configured", async () => {
    const h = harness({ configured: false });
    await h.done;
    expect(h.states.at(-1)).toEqual({ kind: "unconfigured" });
    expect(h.calls).toEqual(["shipped"]);
  });

  it("starts the research for a company nobody has researched, shows its stages, and ends with the record", async () => {
    let polls = 0;
    const h = harness({
      read: async () => {
        polls += 1;
        return polls === 1 ? { state: "none" } : polls < 4 ? { state: "running", stage: `Stage ${polls}`, seconds: polls * 3 } : { state: "ready", record: RECORD };
      },
      start: async () => ({ state: "running", stage: "Finding the company", seconds: 0 }),
    });
    await h.done;
    const kinds = h.states.map((s) => s.kind);
    expect(kinds[0]).toBe("checking");
    expect(kinds).toContain("running");
    expect(h.states.at(-1)).toMatchObject({ kind: "ready", source: "live" });
    expect(h.calls.filter((c) => c === "start")).toHaveLength(1); // it was started once, then watched
    expect(h.states.filter((s) => s.kind === "running").map((s) => s.kind === "running" && s.stage)).toContain("Stage 2");
  });

  it("calls a sleeping engine 'waking' and keeps trying, then goes through once it answers", async () => {
    let tries = 0;
    const h = harness({
      read: async () => {
        tries += 1;
        if (tries <= 3) throw new Error("network");
        return { state: "ready", record: RECORD };
      },
    });
    await h.done;
    const waking = h.states.filter((s) => s.kind === "waking");
    expect(waking).toHaveLength(3);
    expect(waking.map((s) => s.kind === "waking" && s.seconds)).toEqual([0, 5, 10]);
    expect(h.states.at(-1)?.kind).toBe("ready");
  });

  it("gives up on an engine that never wakes, saying offline", async () => {
    const h = harness({ read: async () => Promise.reject(new Error("down")) });
    await h.done;
    expect(h.states.at(-1)).toEqual({ kind: "offline" });
    expect(h.states.filter((s) => s.kind === "waking").length).toBeGreaterThan(10);
  });

  it("reports the reason a job failed and does not retry it", async () => {
    const h = harness({ read: async () => ({ state: "failed", reason: "The research could not be completed (RuntimeError)." }) });
    await h.done;
    expect(h.states.at(-1)).toEqual({ kind: "failed", reason: "The research could not be completed (RuntimeError)." });
    expect(h.calls.filter((c) => c === "read")).toHaveLength(1);
  });

  it("reports a spent daily allowance in the engine's own words", async () => {
    const h = harness({ start: async () => ({ state: "capped", detail: "Today's allowance has been used." }) });
    await h.done;
    expect(h.states.at(-1)).toEqual({ kind: "capped", detail: "Today's allowance has been used." });
  });

  it("stops asking when told to stop", async () => {
    const states: ResearchState[] = [];
    let reads = 0;
    let resolveRead: (() => void) | undefined;
    const stop = runResearchFlow(
      "ACME",
      {
        configured: true,
        now: () => 0,
        sleep: () => new Promise((r) => (resolveRead = r)),
        shipped: async () => null,
        read: async () => (reads++, { state: "running", stage: "Working", seconds: 1 }),
        start: async () => ({ state: "none" }),
      },
      (s) => states.push(s),
    );
    await new Promise((r) => setTimeout(r, 10));
    stop();
    resolveRead?.();
    await new Promise((r) => setTimeout(r, 10));
    expect(reads).toBe(1);
  });
});
