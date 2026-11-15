import { describe, expect, it } from "vitest";
import { alertCount, filingAlerts, filingNote, moveWords, sessionCount, signalAlerts, signalReasons } from "@/lib/alerts";
import type { Settings } from "@/lib/settings";
import type { Brief, Item, Session } from "@/lib/types";

const REF = "2026-11-15T09:00:00+05:30";
const LINES = { windowHours: 24, priceMovePct: 5, volumeMultiple: 2, mutedSymbols: [] as string[] };

function session(day: string, change: number, ratio: number | null): Session {
  return { day, close: 100, prev_close: 100, change_pct: change, volume: 1000, avg_volume: 500, volume_ratio: ratio };
}

function mk(signals: { symbol: string; sessions: Session[] }[], items: Item[] = []): Brief {
  const companies = signals.map((s) => ({ symbol: s.symbol, name: `${s.symbol} Ltd`, sector: "x", size_bucket: "large", stale: {}, errors: {} }));
  return { schema: 1, generated_at: REF, item_days: 14, companies, items, signals };
}

function item(over: Partial<Item> = {}): Item {
  return {
    id: Math.random().toString(36).slice(2), symbol: "AAA", company: "A Ltd", source: "bse", published_at: "2026-11-15T08:00:00+05:30",
    category: "results", category_label: "Results", card_type: "results", priority: 88, routine: false, default_alert: true, why: "",
    tone: "neutral", headline: "h", rule: "r", subject: "s", body: "", raw_category: "", raw_subcategory: "", url: null, size_kb: null, ...over,
  };
}

describe("signalAlerts", () => {
  it("alerts on a move of more than the line, down as bad and up as good", () => {
    const brief = mk([
      { symbol: "DOWN", sessions: [session("2026-11-13", -6, 1)] },
      { symbol: "UP", sessions: [session("2026-11-13", 6, 1)] },
      { symbol: "QUIET", sessions: [session("2026-11-13", 4.9, 1)] },
    ]);
    const alerts = signalAlerts(brief, LINES);
    expect(alerts.map((a) => [a.symbol, a.tone])).toEqual([["DOWN", "bad"], ["UP", "good"]]);
    expect(alerts[0].reasons).toEqual(["price"]);
  });

  it("treats a move exactly on the line as not past it", () => {
    expect(signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", 5, 1)] }]), LINES)).toHaveLength(0);
    expect(signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", 0, 2)] }]), LINES)).toHaveLength(0);
  });

  it("alerts on volume alone as a watch item, and never on a missing ratio", () => {
    const a = signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", 0.4, 2.5)] }]), LINES);
    expect(a).toHaveLength(1);
    expect(a[0].tone).toBe("watch");
    expect(a[0].reasons).toEqual(["volume"]);
    expect(signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", 0.4, null)] }]), LINES)).toHaveLength(0);
  });

  it("names both reasons when price and volume both break the line, and colours by the price", () => {
    const a = signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", -7, 3)] }]), LINES);
    expect(a[0].reasons).toEqual(["price", "volume"]);
    expect(a[0].tone).toBe("bad");
  });

  it("moving a threshold changes the result at once (the step's done-when)", () => {
    const brief = mk([
      { symbol: "A", sessions: [session("2026-11-13", 3.5, 1.2)] },
      { symbol: "B", sessions: [session("2026-11-13", -2.2, 2.4)] },
    ]);
    expect(signalAlerts(brief, LINES)).toHaveLength(1); // only B's volume at the defaults
    expect(signalAlerts(brief, { ...LINES, priceMovePct: 3 })).toHaveLength(2); // A's 3.5% now counts
    expect(signalAlerts(brief, { ...LINES, priceMovePct: 3, volumeMultiple: 3 })).toHaveLength(1); // B's volume no longer does
    expect(signalAlerts(brief, { ...LINES, priceMovePct: 2, volumeMultiple: 3 }).map((a) => a.symbol).sort()).toEqual(["A", "B"]);
  });

  it("reads one session per day of window, from the latest backwards", () => {
    const sessions = ["2026-11-06", "2026-11-09", "2026-11-11", "2026-11-12", "2026-11-13"].map((d) => session(d, -9, 1));
    const brief = mk([{ symbol: "A", sessions }]);
    expect(signalAlerts(brief, { ...LINES, windowHours: 24 }).map((a) => a.session.day)).toEqual(["2026-11-13"]);
    expect(signalAlerts(brief, { ...LINES, windowHours: 72 })).toHaveLength(3);
    expect(signalAlerts(brief, { ...LINES, windowHours: 168 })).toHaveLength(5);
    expect(sessionCount(24)).toBe(1);
    expect(sessionCount(72)).toBe(3);
    expect(sessionCount(168)).toBe(5);
    expect(sessionCount(0)).toBe(1);
    expect(sessionCount(10_000)).toBe(5);
  });

  it("leaves out muted companies", () => {
    const brief = mk([{ symbol: "A", sessions: [session("2026-11-13", -9, 1)] }, { symbol: "B", sessions: [session("2026-11-13", -9, 1)] }]);
    expect(signalAlerts(brief, { ...LINES, mutedSymbols: ["B"] }).map((a) => a.symbol)).toEqual(["A"]);
  });

  it("puts risks first, then the biggest breach, then the newest", () => {
    const brief = mk([
      { symbol: "GOOD", sessions: [session("2026-11-13", 20, 1)] },
      { symbol: "WATCH", sessions: [session("2026-11-13", 0, 9)] },
      { symbol: "BAD_SMALL", sessions: [session("2026-11-13", -6, 1)] },
      { symbol: "BAD_BIG", sessions: [session("2026-11-13", -15, 1)] },
    ]);
    expect(signalAlerts(brief, LINES).map((a) => a.symbol)).toEqual(["BAD_BIG", "BAD_SMALL", "WATCH", "GOOD"]);
  });

  it("measures severity against the user's own line", () => {
    const a = signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", -10, 1)] }]), LINES)[0];
    expect(a.severity).toBe(2);
    expect(signalAlerts(mk([{ symbol: "A", sessions: [session("2026-11-13", -10, 1)] }]), { ...LINES, priceMovePct: 8 })[0].severity).toBe(1.25);
  });
});

describe("filingAlerts", () => {
  const settings = (over: Partial<Settings> = {}): Settings => ({
    windowHours: 24, volumeMultiple: 2, priceMovePct: 5, mutedSymbols: [], alertCategories: { results: true, dividend: false, insider_trading: false }, ...over,
  });

  it("includes only the categories the user switched on", () => {
    const brief = mk([], [item({ id: "r", category: "results" }), item({ id: "d", category: "dividend" })]);
    expect(filingAlerts(brief, settings()).map((i) => i.id)).toEqual(["r"]);
    expect(filingAlerts(brief, settings({ alertCategories: { results: false, dividend: true } })).map((i) => i.id)).toEqual(["d"]);
  });

  it("includes a routine category if the user asked for it", () => {
    const brief = mk([], [item({ id: "i", category: "insider_trading", routine: true })]);
    expect(filingAlerts(brief, settings({ alertCategories: { insider_trading: true } }))).toHaveLength(1);
  });

  it("respects the window and muted companies, and ranks by priority", () => {
    const brief = mk([], [
      item({ id: "old", published_at: "2026-11-01T08:00:00+05:30" }),
      item({ id: "muted", symbol: "BBB" }),
      item({ id: "low", priority: 60 }),
      item({ id: "high", priority: 95 }),
    ]);
    expect(filingAlerts(brief, settings({ mutedSymbols: ["BBB"] })).map((i) => i.id)).toEqual(["high", "low"]);
  });

  it("counts price and filing alerts together for the nav badge", () => {
    const brief = mk([{ symbol: "A", sessions: [session("2026-11-13", -9, 1)] }], [item()]);
    expect(alertCount(brief, settings())).toBe(2);
  });
});

describe("moveWords", () => {
  it("says fell or rose with one decimal", () => {
    expect(moveWords(-5.26)).toBe("fell 5.3%");
    expect(moveWords(7)).toBe("rose 7.0%");
  });
});

describe("signalReasons", () => {
  const alert = (change: number, ratio: number | null, reasons: ("price" | "volume")[]) => ({ session: session("2026-11-13", change, ratio), reasons });
  const lines = { priceMovePct: 5, volumeMultiple: 2 };

  it("states each reason against the reader's own limit, in plain words", () => {
    expect(signalReasons(alert(-6.14, 1, ["price"]), lines)).toEqual(["Price −6.1% · your limit ±5%"]);
    expect(signalReasons(alert(3.8, 3.2, ["volume"]), lines)).toEqual(["Volume 3.2× the 20-day average · your limit 2×"]);
    expect(signalReasons(alert(5.5, 3.2, ["price", "volume"]), { priceMovePct: 4.5, volumeMultiple: 2.5 })).toEqual([
      "Price +5.5% · your limit ±4.5%",
      "Volume 3.2× the 20-day average · your limit 2.5×",
    ]);
  });
});

describe("filingNote", () => {
  const filed = (over: Partial<Item>) => item({ published_at: "2026-11-15T08:00:00+05:30", ...over });

  it("names the material filing the company made that same day", () => {
    expect(filingNote("AAA", "2026-11-15", [filed({})], REF)).toBe("A filing came out today: Results");
    expect(filingNote("AAA", "2026-11-13", [filed({ published_at: "2026-11-13T17:00:00+05:30" })], REF)).toBe("A filing came out that day: Results");
  });

  it("says no filing explains the move when there is none that day, only a routine one, or only another company's", () => {
    expect(filingNote("AAA", "2026-11-15", [], REF)).toBe("No filing explains this move");
    expect(filingNote("AAA", "2026-11-15", [filed({ published_at: "2026-11-14T08:00:00+05:30" })], REF)).toBe("No filing explains this move");
    expect(filingNote("AAA", "2026-11-15", [filed({ routine: true, category: "agm_egm" })], REF)).toBe("No filing explains this move");
    expect(filingNote("AAA", "2026-11-15", [filed({ symbol: "BBB" })], REF)).toBe("No filing explains this move");
  });

  it("counts the day in India, not in UTC, and lists the most important filings first", () => {
    expect(filingNote("AAA", "2026-11-15", [filed({ published_at: "2026-11-15T00:21:18+05:30" })], REF)).toBe("A filing came out today: Results");
    const several = [filed({ category: "m_and_a", priority: 80 }), filed({ category: "results", priority: 88 }), filed({ category: "litigation", priority: 95 })];
    expect(filingNote("AAA", "2026-11-15", several, REF)).toBe("A filing came out today: Legal, Results and 1 more");
  });
});

