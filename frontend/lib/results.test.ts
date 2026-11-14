import { describe, expect, it } from "vitest";
import { basisLabel, checkView, formatCrore, formatDelta, marginLines, metricRows, pagesLabel, printedLine, unitNote } from "@/lib/results";
import type { CardMetric, ResultsCard } from "@/lib/types";

type Readable = Exclude<ResultsCard, { status: "failed" }>;

function metric(over: Partial<CardMetric> & Pick<CardMetric, "key">): CardMetric {
  return {
    label: over.key,
    current: 100,
    previous: 90,
    year_ago: 80,
    qoq_pct: 11.1,
    yoy_pct: 25,
    qoq_swing: null,
    yoy_swing: null,
    printed: { label: "Revenue from operations", page: 8, tokens: ["100.00", "90.00", "80.00"] },
    ...over,
  };
}

function card(over: Partial<Readable> = {}): Readable {
  return {
    type: "results",
    status: "ok",
    verification: null,
    basis: "consolidated",
    unit_printed: "crore",
    period: { label: "Q2 FY27", current: "2026-09-30", previous: "2026-06-30", year_ago: "2025-09-30" },
    source: { url: "https://example.test/x.pdf", pages: [8] },
    metrics: [metric({ key: "revenue" })],
    margins: { pbt: { current: 20, year_ago: 17.5 } },
    warnings: [],
    check: { status: "ok", against: "Yahoo Finance quarterly figures", note: "Matches Yahoo Finance for the same quarter." },
    tone: "good",
    tone_reason: "Profit up 43% from a year ago; revenue up 25%",
    extractor: "2",
    ...over,
  };
}

describe("formatCrore", () => {
  it("groups in the Indian way above a thousand and keeps one decimal below", () => {
    expect(formatCrore(332861)).toBe("3,32,861");
    expect(formatCrore(30578.4)).toBe("30,578");
    expect(formatCrore(952.5)).toBe("952.5");
    expect(formatCrore(64.66)).toBe("64.7");
  });
  it("uses a real minus sign and never shows a negative zero", () => {
    expect(formatCrore(-39.2)).toBe("−39.2");
    expect(formatCrore(-0.04)).toBe("0.0");
  });
  it("shows a dash for a figure that could not be read", () => {
    expect(formatCrore(null)).toBe("—");
  });
});

describe("formatDelta", () => {
  it("points up or down with the size", () => {
    expect(formatDelta(4.4, null)).toEqual({ text: "▲ 4.4%", direction: "up" });
    expect(formatDelta(-65.6, null)).toEqual({ text: "▼ 65.6%", direction: "down" });
    expect(formatDelta(1234.56, null).text).toBe("▲ 1,234.6%");
  });
  it("names a swing between profit and loss instead of giving a percentage", () => {
    expect(formatDelta(null, "turned profit")).toEqual({ text: "▲ to profit", direction: "up" });
    expect(formatDelta(null, "turned loss")).toEqual({ text: "▼ to loss", direction: "down" });
    expect(formatDelta(12, "turned loss").direction).toBe("down"); // a swing outranks a number
  });
  it("shows a dash when there is nothing to compare, and a flat move without an arrow", () => {
    expect(formatDelta(null, null)).toEqual({ text: "—", direction: "none" });
    expect(formatDelta(0.04, null)).toEqual({ text: "0.0%", direction: "flat" });
  });
});

describe("the check badge", () => {
  const base = { against: "Yahoo Finance quarterly figures", note: "" };
  it("always has words next to its icon, and says what it rests on", () => {
    const ok = checkView({
      ...base,
      status: "ok",
      note: "Matches Yahoo Finance for the same quarter.",
      details: [
        { metric: "revenue", filing: 1000, yahoo: 1000, diff_pct: 0, ok: true },
        { metric: "pbt", filing: 200, yahoo: 199, diff_pct: 0.5, ok: true },
      ],
    });
    expect(ok).toEqual({ icon: "✓", title: "Matches Yahoo Finance", tone: "good", lines: ["Same quarter; checked revenue, PBT."] });
    expect(checkView({ ...base, status: "unavailable", note: "Yahoo has not published this quarter yet." })).toEqual({
      icon: "–",
      title: "Not cross-checked",
      tone: "neutral",
      lines: ["Yahoo has not published this quarter yet."],
    });
  });
  it("shows how far apart the numbers are when they differ, and keeps the caution", () => {
    const view = checkView({
      ...base,
      status: "differs",
      note: "The filing is the source of truth.",
      details: [
        { metric: "revenue", filing: 1000, yahoo: 1000, diff_pct: 0, ok: true },
        { metric: "pbt", filing: 647.3, yahoo: 700.1, diff_pct: 7.5, ok: false },
      ],
    });
    expect(view).toMatchObject({ icon: "⚠", title: "Differs from Yahoo Finance", tone: "watch" });
    expect(view.lines).toEqual(["PBT: filing 647.3 against Yahoo 700.1 crore (7.5% apart)", "The filing is the source of truth."]);
  });
  it("says nothing extra for a pass that has no details", () => {
    expect(checkView({ ...base, status: "ok" }).lines).toEqual([]);
  });
});

describe("metricRows", () => {
  it("abbreviates PBT and PAT with the full name kept for a tooltip, and flags computed figures", () => {
    const rows = metricRows(
      card({ metrics: [metric({ key: "pbt" }), metric({ key: "ebitda", derived: "Computed here, not reported" }), metric({ key: "revenue", current: null })] }),
    );
    expect(rows[0]).toMatchObject({ text: "PBT", full: "Profit before tax", current: "100.0", derived: null });
    expect(metricRows(card({ metrics: [metric({ key: "pat_owners" })] }))[0]).toMatchObject({ text: "Owners' PAT" });
    expect(rows[1]).toMatchObject({ text: "EBITDA", derived: "Computed here, not reported" });
    expect(rows[2].current).toBe("—");
    expect(rows[0].qoq.text).toBe("▲ 11.1%");
  });
});

describe("the small labels", () => {
  it("writes margins with last year's where it exists", () => {
    const lines = marginLines(card({ margins: { ebitda: { current: 12.6, year_ago: 16.1 }, pbt: { current: 20, year_ago: null }, pat: { current: null, year_ago: 5 } } }));
    expect(lines).toEqual(["EBITDA margin 12.6%, was 16.1% a year ago", "PBT margin 20.0%"]);
  });
  it("shows the printed figures, or says a figure is computed", () => {
    expect(printedLine(metric({ key: "revenue" }))).toBe("“Revenue from operations”, page 8: 100.00  ·  90.00  ·  80.00");
    expect(printedLine(metric({ key: "pat", printed: { label: "PROFIT FOR THE PERIOD", page: 9, tokens: [null, "4508.79", null] } }))).toBe(
      "“PROFIT FOR THE PERIOD”, page 9: —  ·  4508.79  ·  —",
    );
    expect(printedLine(metric({ key: "ebitda", printed: { label: "computed", page: 8, tokens: [] } }))).toMatch(/Computed here/);
  });
  it("labels pages, basis and a converted unit", () => {
    expect(pagesLabel([8])).toBe("page 8");
    expect(pagesLabel([8, 9])).toBe("pages 8, 9");
    expect(pagesLabel([])).toBe("");
    expect(basisLabel("consolidated")).toBe("Consolidated");
    expect(basisLabel("not stated")).toBe("Basis not stated");
    expect(unitNote("crore")).toBeNull();
    expect(unitNote(null)).toBeNull();
    expect(unitNote("million")).toBe("The filing prints its figures in ₹ million; they are shown here in ₹ crore.");
  });
});
