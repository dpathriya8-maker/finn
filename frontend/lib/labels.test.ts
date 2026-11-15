import { describe, expect, it } from "vitest";
import { shortCategory, shortWhy } from "@/lib/labels";
// Every category the pipeline ships (a copy of config/categories.json, inside frontend/ so a deploy of this folder alone can see it),
// so a new category cannot silently fall to "Other".
import config from "../public/data/config.json";

describe("shortCategory", () => {
  it("uses the short labels the Brief shows", () => {
    const label = (category: string, routine = false) => shortCategory({ category, routine });
    expect(label("results")).toBe("Results");
    expect(label("m_and_a")).toBe("M&A");
    expect(label("management_change")).toBe("People");
    expect(label("fund_raise")).toBe("Fund raise");
    expect(label("litigation")).toBe("Legal");
    expect(label("credit_rating")).toBe("Rating");
    expect(label("dividend")).toBe("Dividend");
    expect(label("pledging")).toBe("Pledge");
    expect(label("agm_egm", true)).toBe("Meeting");
    expect(label("investor_meetings", true)).toBe("Meeting");
  });

  it("calls an unmapped routine filing Routine and anything else unmapped Other", () => {
    expect(shortCategory({ category: "insider_trading", routine: true })).toBe("Routine");
    expect(shortCategory({ category: "something_new", routine: true })).toBe("Routine");
    expect(shortCategory({ category: "unclassified", routine: false })).toBe("Other");
  });

  it("is short enough for a phone for every configured category", () => {
    for (const c of config.categories) {
      const text = shortCategory({ category: c.id, routine: c.is_routine });
      expect(text.length).toBeGreaterThan(0);
      expect(text.length).toBeLessThanOrEqual(10);
    }
  });
});

describe("shortWhy", () => {
  const why = (text: string, category = "unclassified", card: Parameters<typeof shortWhy>[0]["card"] = undefined) => shortWhy({ why: text, category, card });
  const metric = (key: "revenue" | "pat", yoy_pct: number | null, yoy_swing: "turned profit" | "turned loss" | null = null) => ({
    key, label: key, current: 1, previous: 1, year_ago: 1, qoq_pct: null, yoy_pct, qoq_swing: null, yoy_swing, printed: { label: "", page: 1, tokens: [] },
  });
  const results = (metrics: ReturnType<typeof metric>[]) => ({
    type: "results" as const, status: "ok" as const, verification: null, basis: "consolidated" as const, unit_printed: null,
    period: { label: "Q2 FY27", current: null, previous: null, year_ago: null }, source: { url: null, pages: [] },
    metrics, margins: {}, warnings: [], check: { status: "ok" as const, against: "", note: "" },
    tone: "neutral" as const, tone_reason: "", extractor: "",
  });
  const LONG = "Weaker than a year ago, so it ranks higher. Quarterly results are the most material filing";

  it("says what happened to profit, from the figures, on a results card", () => {
    expect(why(LONG, "results", results([metric("revenue", 4), metric("pat", -66)]))).toBe("Profit fell vs last year");
    expect(why(LONG, "results", results([metric("pat", 16)]))).toBe("Profit rose vs last year");
    expect(why(LONG, "results", results([metric("pat", null, "turned loss")]))).toBe("Profit turned to a loss");
    expect(why(LONG, "results", results([metric("pat", null, "turned profit")]))).toBe("Profit turned positive");
    expect(why(LONG, "results", results([metric("pat", 0.2)]))).toBe("Profit flat vs last year");
  });

  it("falls back to revenue when profit was not read, and to the note when neither was", () => {
    expect(why(LONG, "results", results([metric("revenue", -7)]))).toBe("Revenue fell vs last year");
    expect(why(LONG, "results", results([]))).toBe("Weaker than a year ago");
  });

  it("uses the filing-specific note first, then what the category means", () => {
    expect(why("Order win. Company news", "press_release")).toBe("Order win");
    expect(why("Board meeting outcome. Could not be classified, so it is shown rather than hidden")).toBe("Board meeting outcome");
    expect(why("Changes what the company is", "m_and_a")).toBe("Changes what the company is");
    expect(why("Routine: Newspaper copy of an earlier filing", "press_release")).toBe("Newspaper copy of an earlier filing");
  });

  it("cuts a ranking explanation at the colon and a long category line at the clause", () => {
    expect(why("A key person is leaving: exits rank above hires. Leadership changes move stocks", "management_change")).toBe("A key person is leaving");
    expect(why("Could not be classified, so it is shown rather than hidden")).toBe("Could not be classified");
  });

  it("keeps every line to about eight words", () => {
    expect(why("Legal or regulatory action can move a stock fast", "litigation")).toBe("Legal action can move a stock fast");
    const cut = why("One two three four five six seven eight nine ten");
    expect(cut).toBe("One two three four five six seven eight…");
    for (const text of [LONG, "Raising money can dilute shareholders or add debt", "Ratings affect what the company pays to borrow"]) {
      expect(why(text).split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(9);
    }
  });
});
