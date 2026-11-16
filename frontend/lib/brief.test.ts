import { describe, expect, it } from "vitest";
import { companySections, effectiveWindow, GROUP_LIMIT, groupByCompany, groupItems, selectItems, staleNotes, summaryLine, thingsThatMatter, whenLabel } from "@/lib/brief";
import type { Brief, Item } from "@/lib/types";

const REF = "2026-11-15T09:00:00+05:30";

function item(over: Partial<Item> = {}): Item {
  return {
    id: "x", symbol: "AAA", company: "A Ltd", source: "bse", published_at: "2026-11-15T08:00:00+05:30",
    category: "press_release", category_label: "Press release", card_type: "one_liner", priority: 50, routine: false,
    default_alert: false, why: "", tone: "neutral", headline: "h", rule: "r", subject: "s", body: "",
    raw_category: "", raw_subcategory: "", url: null, size_kb: null, ...over,
  };
}

function brief(items: Item[], companies: Brief["companies"] = []): Brief {
  return { schema: 1, generated_at: REF, item_days: 14, companies, items, signals: [] };
}

const hoursBefore = (h: number) => new Date(Date.parse(REF) - h * 3_600_000).toISOString();

describe("selectItems", () => {
  it("keeps what falls inside the window and drops the rest", () => {
    const b = brief([item({ id: "in", published_at: hoursBefore(23) }), item({ id: "out", published_at: hoursBefore(25) })]);
    expect(selectItems(b, 24).map((i) => i.id)).toEqual(["in"]);
    expect(selectItems(b, 72).map((i) => i.id).sort()).toEqual(["in", "out"]);
  });

  it("counts the window back from the data's own time, so a stale file is not empty", () => {
    const old: Brief = { ...brief([item({ published_at: "2026-01-01T10:00:00+05:30" })]), generated_at: "2026-01-01T12:00:00+05:30" };
    expect(selectItems(old, 24)).toHaveLength(1);
  });

  it("drops muted companies", () => {
    const b = brief([item({ id: "a", symbol: "AAA" }), item({ id: "b", symbol: "BBB" })]);
    expect(selectItems(b, 24, ["BBB"]).map((i) => i.id)).toEqual(["a"]);
  });
});

describe("groupItems", () => {
  it("splits at the priority thresholds and keeps routine filings apart whatever their priority", () => {
    const g = groupItems([
      item({ id: "p90", priority: 90 }), item({ id: "p75", priority: 75 }), item({ id: "p74", priority: 74 }),
      item({ id: "p45", priority: 45 }), item({ id: "p44", priority: 44 }), item({ id: "r99", priority: 99, routine: true }),
    ]);
    expect(g.high.map((i) => i.id)).toEqual(["p90", "p75"]);
    expect(g.medium.map((i) => i.id)).toEqual(["p74", "p45"]);
    expect(g.low.map((i) => i.id)).toEqual(["p44"]);
    expect(g.routine.map((i) => i.id)).toEqual(["r99"]);
  });

  it("puts the most important first, and the newest first among equals", () => {
    const g = groupItems([
      item({ id: "old80", priority: 80, published_at: hoursBefore(10) }),
      item({ id: "new80", priority: 80, published_at: hoursBefore(1) }),
      item({ id: "top", priority: 95, published_at: hoursBefore(20) }),
    ]);
    expect(g.high.map((i) => i.id)).toEqual(["top", "new80", "old80"]);
  });

  it("counts what matters as the high and medium groups only", () => {
    const g = groupItems([item({ priority: 90 }), item({ priority: 60 }), item({ priority: 20 }), item({ routine: true })]);
    expect(thingsThatMatter(g)).toBe(2);
  });

  it("never shows more than five at a time", () => {
    expect(GROUP_LIMIT).toBe(5);
  });
});

describe("groupByCompany", () => {
  it("shows a company once, with its filings under it, most important first", () => {
    const g = groupItems([
      item({ id: "a-low", symbol: "AAA", priority: 50 }),
      item({ id: "b", symbol: "BBB", priority: 80 }),
      item({ id: "a-top", symbol: "AAA", priority: 90 }),
    ]);
    const companies = groupByCompany([...g.high, ...g.medium]);
    expect(companies.map((c) => [c.symbol, c.items.map((i) => i.id)])).toEqual([
      ["AAA", ["a-top", "a-low"]],
      ["BBB", ["b"]],
    ]);
  });

  it("orders companies by their highest-priority filing, so one risk lifts the whole company", () => {
    const g = groupItems([
      item({ id: "x1", symbol: "XXX", priority: 60 }),
      item({ id: "x2", symbol: "XXX", priority: 55 }),
      item({ id: "x3", symbol: "XXX", priority: 50 }),
      item({ id: "y1", symbol: "YYY", priority: 95, tone: "bad" }),
    ]);
    expect(groupByCompany([...g.high, ...g.medium]).map((c) => c.symbol)).toEqual(["YYY", "XXX"]);
  });

  it("splits companies into the two sections by their top filing, keeping routine and low filings out", () => {
    const g = groupItems([
      item({ id: "hi", symbol: "AAA", priority: 90 }),
      item({ id: "mid", symbol: "AAA", priority: 50 }),
      item({ id: "only-mid", symbol: "BBB", priority: 60 }),
      item({ id: "low", symbol: "CCC", priority: 40 }),
      item({ id: "routine", symbol: "DDD", priority: 99, routine: true }),
    ]);
    const s = companySections(g);
    expect(s.needs.map((c) => [c.symbol, c.items.length])).toEqual([["AAA", 2]]);
    expect(s.worth.map((c) => c.symbol)).toEqual(["BBB"]);
    expect(g.low.map((i) => i.id)).toEqual(["low"]);
    expect(g.routine.map((i) => i.id)).toEqual(["routine"]);
  });

  it("keeps the count of things that matter as a count of filings", () => {
    const g = groupItems([item({ symbol: "AAA", priority: 90 }), item({ symbol: "AAA", priority: 60 }), item({ symbol: "BBB", priority: 50 })]);
    expect(thingsThatMatter(g)).toBe(3);
    const s = companySections(g);
    expect(s.needs.length + s.worth.length).toBe(2);
  });
});

describe("summaryLine", () => {
  const line = (items: Item[], n = 18) => summaryLine(groupItems(items), n);

  it("says the day was quiet when nothing is material, however many routine filings there are", () => {
    expect(line([])).toBe("Quiet day: nothing needs action across your 18 companies");
    expect(line([item({ routine: true, priority: 99 }), item({ priority: 20 })], 1)).toBe("Quiet day: nothing needs action across your 1 company");
  });

  it("counts the material filings tagged Risk", () => {
    expect(line([item({ priority: 90, tone: "bad" })])).toBe("1 risk to review");
    expect(line([item({ priority: 90, tone: "bad" }), item({ symbol: "BBB", priority: 60, tone: "bad" }), item({ symbol: "CCC", priority: 60, tone: "good" })])).toBe("2 risks to review");
  });

  it("calls it busy when five or more companies have something material, and joins the two parts", () => {
    const five = ["A", "B", "C", "D", "E"].map((symbol) => item({ symbol, priority: 80 }));
    expect(line(five)).toBe("Busy day: 5 of your companies filed");
    expect(line(five.slice(0, 4))).toBe("4 filings worth a look");
    expect(line([...five, item({ symbol: "F", priority: 95, tone: "bad" })])).toBe("1 risk to review · Busy day: 6 of your companies filed");
  });

  it("counts companies, not filings, for a busy day", () => {
    const many = Array.from({ length: 8 }, (_, i) => item({ id: `x${i}`, symbol: i < 4 ? "AAA" : "BBB", priority: 80 }));
    expect(line(many)).toBe("8 filings worth a look");
  });
});

describe("whenLabel", () => {
  it("says Today, Yesterday or the date, counted from the data's time", () => {
    expect(whenLabel("2026-11-15T08:00:00+05:30", REF)).toMatch(/^Today, 8:00\sam$/i);
    expect(whenLabel("2026-11-14T18:23:00+05:30", REF)).toMatch(/^Yesterday, 6:23\spm$/i);
    expect(whenLabel("2026-11-10T11:00:00+05:30", REF)).toMatch(/^10 Nov, 11:00\sam$/i);
  });

  it("uses India's calendar day, not UTC's", () => {
    // 23:54 IST on the 14th and 00:30 IST on the 15th share a UTC date but not an Indian one.
    expect(whenLabel("2026-11-14T23:54:00+05:30", "2026-11-15T00:30:00+05:30")).toMatch(/^Yesterday, 11:54\spm$/i);
  });

  it("returns nothing for a timestamp it cannot read", () => {
    expect(whenLabel("not a date", REF)).toBe("");
  });
});

describe("staleNotes", () => {
  it("names the company and the part that is showing old data", () => {
    const b = brief([], [
      { symbol: "AAA", name: "A", sector: "s", size_bucket: "large", errors: {}, stale: { announcements: "2026-11-14T18:00:00+05:30" } },
      { symbol: "BBB", name: "B", sector: "s", size_bucket: "large", errors: {}, stale: {} },
    ]);
    expect(staleNotes(b)).toEqual([expect.stringMatching(/^AAA: announcements as of Yesterday, 6:00\spm$/i)]);
  });

  it("is empty when everything is fresh", () => {
    expect(staleNotes(brief([]))).toEqual([]);
  });
});

describe("effectiveWindow (the Brief never opens on an empty day if a wider window has something)", () => {
  const material = (id: string, hours: number) => item({ id, priority: 80, published_at: hoursBefore(hours) });

  it("keeps the reader's own choice, even if it is empty", () => {
    const b = brief([material("m", 50)]);
    expect(effectiveWindow(b, 24, true)).toEqual({ hours: 24, widened: false });
  });

  it("keeps the default when it already has something material", () => {
    const b = brief([material("m", 5)]);
    expect(effectiveWindow(b, 24, false)).toEqual({ hours: 24, widened: false });
  });

  it("looks back to 3 days, then to 7, when the default holds nothing material, and says it widened", () => {
    expect(effectiveWindow(brief([material("m", 50)]), 24, false)).toEqual({ hours: 72, widened: true });
    expect(effectiveWindow(brief([material("m", 100)]), 24, false)).toEqual({ hours: 168, widened: true });
  });

  it("does not count routine or low filings as material", () => {
    const b = brief([item({ id: "r", routine: true, priority: 90, published_at: hoursBefore(2) }), item({ id: "l", priority: 10, published_at: hoursBefore(2) }), material("m", 50)]);
    expect(effectiveWindow(b, 24, false)).toEqual({ hours: 72, widened: true });
  });

  it("stays on the default when nothing is material in any window", () => {
    expect(effectiveWindow(brief([material("m", 400)]), 24, false)).toEqual({ hours: 24, widened: false });
    expect(effectiveWindow(brief([]), 24, false)).toEqual({ hours: 24, widened: false });
  });

  it("ignores muted companies and never looks at the device's clock", () => {
    const b = brief([item({ id: "m", symbol: "ITC", priority: 80, published_at: hoursBefore(5) }), material("n", 50)]);
    expect(effectiveWindow(b, 24, false, ["ITC"])).toEqual({ hours: 72, widened: true });
  });
});
