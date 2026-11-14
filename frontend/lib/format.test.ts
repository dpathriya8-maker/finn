import { describe, expect, it } from "vitest";
import { formatDay, formatIst, formatMove, formatPrice, formatShares } from "@/lib/format";

describe("formatPrice", () => {
  it("uses rupees with two decimals and Indian digit grouping", () => {
    expect(formatPrice(1339.7)).toBe("₹1,339.70");
    expect(formatPrice(124567)).toBe("₹1,24,567.00");
    expect(formatPrice(0.5)).toBe("₹0.50");
  });
});

describe("formatShares", () => {
  it("says lakh and crore the way the market does", () => {
    expect(formatShares(13_800_000)).toBe("1.38 crore");
    expect(formatShares(1_380_000)).toBe("13.8 lakh");
    expect(formatShares(99_999)).toBe("99,999");
  });
});

describe("formatMove", () => {
  it("marks direction with an arrow and a flat day with none", () => {
    expect(formatMove(5.26)).toBe("▲ 5.3%");
    expect(formatMove(-0.55)).toBe("▼ 0.6%");
    expect(formatMove(0)).toBe("0.0%");
  });
});

describe("formatDay", () => {
  it("gives the weekday, day and month for a trading day", () => {
    expect(formatDay("2026-11-13")).toBe("Fri 13 Nov");
    expect(formatDay("2026-11-09")).toBe("Mon 9 Nov");
  });
  it("hands back what it cannot read", () => {
    expect(formatDay("nonsense")).toBe("nonsense");
  });
});

describe("formatIst", () => {
  it("writes India time and survives bad input", () => {
    expect(formatIst("2026-11-15T01:50:00+05:30")).toMatch(/^15 Nov, 1:50\sam IST$/i);
    expect(formatIst("garbage")).toBe("an unknown time");
  });
});
