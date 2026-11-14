import { describe, expect, it } from "vitest";
import { GROUP_LIMIT, groupItems, selectItems, staleNotes, thingsThatMatter, whenLabel } from "@/lib/brief";
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
