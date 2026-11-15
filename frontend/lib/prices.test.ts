import { describe, expect, it } from "vitest";
import { highlightsTitle } from "@/lib/brief";
import { cardHeadline, filingHeadline, hueFor, initials, shortName } from "@/lib/headline";
import { closeCaption, completeSessions, moveLook, priceView, sparkPoints, trendLabel } from "@/lib/prices";
import type { Session } from "@/lib/types";

function session(day: string, close: number, change_pct = 0): Session {
  return { day, close, prev_close: close, change_pct, volume: 1000, avg_volume: 1000, volume_ratio: 1 };
}
const DAYS = ["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"];
const SESSIONS = DAYS.map((d, i) => session(d, 100 + i * 2, i === 3 ? -1.02 : 0.5));

describe("price chip", () => {
  it("shows the latest close and its move, and the trend over everything stored", () => {
    const view = priceView(SESSIONS, "2026-11-15T01:30:00+05:30");
    expect(view?.close).toBe(106);
    expect(view?.changePct).toBe(-1.02);
    expect(view?.day).toBe("2026-11-13");
    expect(view?.trendPct).toBeCloseTo(6, 5);
    expect(trendLabel(view!)).toBe("4-day price trend, up 6.0%");
  });
  it("shows nothing without data", () => {
    expect(priceView(undefined)).toBeNull();
    expect(priceView([])).toBeNull();
  });
  it("leaves out a session that is still being traded when the data was made", () => {
    const today = [...SESSIONS, session("2026-11-14", 120, 5)];
    expect(completeSessions(today, "2026-11-14T11:00:00+05:30").map((s) => s.day)).toEqual(DAYS); // 11 am: the market is open
    expect(completeSessions(today, "2026-11-14T18:00:00+05:30").map((s) => s.day)).toEqual([...DAYS, "2026-11-14"]); // 6 pm: it has closed
    expect(priceView(today, "2026-11-14T11:00:00+05:30")?.close).toBe(106);
  });
  it("words the move with an arrow and two decimals, grey when flat", () => {
    expect(moveLook(1.0234)).toEqual({ text: "▲ 1.02%", tone: "good" });
    expect(moveLook(-1.0234)).toEqual({ text: "▼ 1.02%", tone: "bad" });
    expect(moveLook(0)).toEqual({ text: "0.00%", tone: "flat" });
    expect(moveLook(-0.001)).toEqual({ text: "0.00%", tone: "flat" });
  });
  it("names the day of the close", () => {
    expect(closeCaption("2026-11-13")).toBe("13 Nov close");
  });
  it("draws the lowest close at the bottom and the highest at the top", () => {
    const points = sparkPoints([10, 20, 15], 64, 20).split(" ").map((p) => p.split(",").map(Number));
    expect(points).toHaveLength(3);
    expect(points[0][1]).toBeGreaterThan(points[1][1]); // 10 is lower on the page (larger y) than 20
    expect(sparkPoints([5], 64, 20)).toBe("");
    expect(sparkPoints([5, 5], 64, 20)).toContain("10.0"); // a flat line sits in the middle
  });
});

describe("company names and headlines", () => {
  it("shortens the legal name", () => {
    expect(shortName("Reliance Industries Ltd")).toBe("Reliance Industries");
    expect(shortName("Info Edge (India) Ltd")).toBe("Info Edge");
    expect(shortName("Hindustan Aeronautics Limited")).toBe("Hindustan Aeronautics");
    expect(shortName("Ltd")).toBe("Ltd");
  });
  it("takes two initials and a stable hue", () => {
    expect(initials("Bajaj Finance Ltd")).toBe("BF");
    expect(initials("Infosys Ltd")).toBe("IN");
    expect(hueFor("INFY")).toBe(hueFor("INFY"));
    expect(hueFor("INFY")).toBeGreaterThanOrEqual(0);
    expect(hueFor("INFY")).toBeLessThan(360);
  });
  it("leads with the short name, then the fact, within about 70 characters", () => {
    const item = { company: "Trent Ltd", headline: "Credit rating reaffirmed at AA+ by CRISIL for the long-term bank facilities of the company", card: undefined };
    const text = cardHeadline(item);
    expect(text.startsWith("Trent: Credit rating reaffirmed")).toBe(true);
    expect(text.length).toBeLessThanOrEqual(70);
    expect(text.endsWith("…")).toBe(true);
  });
  it("does not say the name twice", () => {
    expect(cardHeadline({ company: "Trent Ltd", headline: "Trent: fixes a date for its AGM", card: undefined })).toBe("Trent: fixes a date for its AGM");
  });
  it("says what changed on a results card, from the figures", () => {
    const metric = (key: "revenue" | "pat", yoy_pct: number | null, yoy_swing: "turned profit" | "turned loss" | null = null) => ({
      key, label: key, current: 1, previous: 1, year_ago: 1, qoq_pct: null, yoy_pct, qoq_swing: null, yoy_swing, printed: { label: "", page: 1, tokens: [] },
    });
    const card = {
      type: "results" as const, status: "ok" as const, verification: null, basis: "consolidated" as const, unit_printed: null,
      period: { label: "Q2 FY27", current: null, previous: null, year_ago: null }, source: { url: null, pages: [] },
      metrics: [metric("revenue", 12.34), metric("pat", -3.1)], margins: {}, warnings: [], check: { status: "ok" as const, against: "", note: "" },
      tone: "neutral" as const, tone_reason: "", extractor: "",
    };
    expect(cardHeadline({ company: "ITC Ltd", headline: "x", card })).toBe("ITC Q2 FY27: revenue ▲\u00a012.3%, profit ▼\u00a03.1% YoY");
  });
});

describe("the headline of a filing under its company's header", () => {
  it("leaves the company's name out, because the header already says it", () => {
    expect(filingHeadline({ company: "Trent Ltd", headline: "Trent: fixes a date for its AGM", card: undefined })).toBe("fixes a date for its AGM");
    expect(filingHeadline({ company: "Trent Ltd", headline: "Execution of Joint Venture", card: undefined })).toBe("Execution of Joint Venture");
  });
  it("keeps a long subject to about two phone lines", () => {
    const text = filingHeadline({ company: "Trent Ltd", headline: "Credit rating reaffirmed at AA+ by CRISIL for the long-term bank facilities of the company and its subsidiaries", card: undefined });
    expect(text.length).toBeLessThanOrEqual(84);
    expect(text.endsWith("…")).toBe(true);
  });
  it("says what changed on a results filing, from the figures, without the name", () => {
    const metric = (key: "revenue" | "pat", yoy_pct: number | null) => ({
      key, label: key, current: 1, previous: 1, year_ago: 1, qoq_pct: null, yoy_pct, qoq_swing: null, yoy_swing: null, printed: { label: "", page: 1, tokens: [] },
    });
    const card = {
      type: "results" as const, status: "ok" as const, verification: null, basis: "consolidated" as const, unit_printed: null,
      period: { label: "Q2 FY27", current: null, previous: null, year_ago: null }, source: { url: null, pages: [] },
      metrics: [metric("revenue", 12.34), metric("pat", -3.1)], margins: {}, warnings: [], check: { status: "ok" as const, against: "", note: "" },
      tone: "neutral" as const, tone_reason: "", extractor: "",
    };
    expect(filingHeadline({ company: "ITC Ltd", headline: "x", card })).toBe("Q2 FY27: revenue ▲\u00a012.3%, profit ▼\u00a03.1% YoY");
  });
  it("falls back to the exchange's words when the results could not be read", () => {
    const failed = { type: "results" as const, status: "failed" as const, reason: "scanned", extractor: "" };
    expect(filingHeadline({ company: "ITC Ltd", headline: "Financial Results", card: failed })).toBe("Financial Results");
  });
});

describe("the Brief heading", () => {
  it("says today for a day and names a longer window", () => {
    expect(highlightsTitle(24)).toBe("Today's Highlights");
    expect(highlightsTitle(72)).toBe("Highlights: last 3 days");
    expect(highlightsTitle(168)).toBe("Highlights: last 7 days");
  });
});
