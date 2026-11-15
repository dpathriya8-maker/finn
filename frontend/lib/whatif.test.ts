import { describe, expect, it } from "vitest";
import { parseAmountInput } from "@/lib/invested";
import { ariaValueText, arrowPct, changeRow, periodChange, rupeeChange, scenario, signedInr, signedPct } from "@/lib/whatif";
import type { Session } from "@/lib/types";

const S = (day: string, close: number): Session => ({ day, close, prev_close: close, change_pct: 0, volume: 1, avg_volume: 1, volume_ratio: 1 });

describe("gains and losses in rupees", () => {
  it("is the amount times the move, in whole rupees", () => {
    expect(rupeeChange(10000, -1.55)).toBe(-155);
    expect(rupeeChange(10000, 4.2)).toBe(420);
    expect(rupeeChange(10000, -10)).toBe(-1000);
    expect(rupeeChange(333, 1)).toBe(3); // 3.33 rounds to 3
  });

  it("writes the sign every time, with a real minus and Indian grouping", () => {
    expect(signedInr(420)).toBe("+₹420");
    expect(signedInr(-155)).toBe("−₹155");
    expect(signedInr(150000)).toBe("+₹1,50,000");
    expect(signedInr(-12345678)).toBe("−₹1,23,45,678");
  });

  it("puts the arrow in the number, so colour is never the only signal", () => {
    expect(arrowPct(-1.55)).toBe("▼1.55%");
    expect(arrowPct(4.2, 1)).toBe("▲4.2%");
    expect(changeRow("Today", -1.55, 10000)).toEqual({ label: "Today (▼1.55%)", text: "−₹155", tone: "bad" });
    expect(changeRow("Last 30 days", 4.2, 10000, 1)).toEqual({ label: "Last 30 days (▲4.2%)", text: "+₹420", tone: "good" });
  });
});

describe("no move, no amount, a huge amount", () => {
  it("treats 0% as no change, never as a gain or a loss", () => {
    expect(rupeeChange(10000, 0)).toBe(0);
    expect(Object.is(rupeeChange(10000, -0), 0)).toBe(true); // not "-0"
    expect(arrowPct(0)).toBe("0.00%");
    expect(arrowPct(0.001)).toBe("0.00%"); // rounds to nothing, so no arrow either
    expect(changeRow("Today", 0, 10000)).toEqual({ label: "Today (0.00%)", text: "₹0", tone: "flat" });
    expect(scenario(10000, 0)).toEqual({ change: 0, total: 10000, tone: "flat" });
    expect(signedPct(0)).toBe("0%");
  });

  it("is zero rupees for a zero amount, and ignores what is not a number", () => {
    expect(rupeeChange(0, 20)).toBe(0);
    expect(scenario(0, -20)).toEqual({ change: 0, total: 0, tone: "flat" });
    expect(rupeeChange(Number.NaN, 5)).toBe(0);
    expect(rupeeChange(100, Number.NaN)).toBe(0);
    expect(scenario(Number.NaN, 5).total).toBe(0);
  });

  it("reads what people type, and an empty or bad box gives no amount at all", () => {
    expect(parseAmountInput("")).toEqual({ value: null, valid: true }); // empty: the calculator asks for an amount
    expect(parseAmountInput("₹1,50,000")).toEqual({ value: 150000, valid: true });
    expect(parseAmountInput("-5").valid).toBe(false);
    expect(parseAmountInput("abc").valid).toBe(false);
  });

  it("stays exact at the largest amount accepted (₹1 lakh crore)", () => {
    const big = 1_000_000_000_000;
    expect(parseAmountInput(String(big)).valid).toBe(true);
    expect(parseAmountInput(String(big + 1)).valid).toBe(false);
    expect(scenario(big, -20)).toEqual({ change: -200_000_000_000, total: 800_000_000_000, tone: "bad" });
    expect(signedInr(rupeeChange(big, 20))).toBe("+₹2,00,00,00,00,000");
  });
});

describe("the slider", () => {
  it("says what the amount becomes", () => {
    expect(scenario(10000, -10)).toEqual({ change: -1000, total: 9000, tone: "bad" });
    expect(scenario(10000, 5)).toEqual({ change: 500, total: 10500, tone: "good" });
    expect(signedPct(-10)).toBe("−10%");
    expect(signedPct(5)).toBe("+5%");
  });

  it("is spoken in words for a screen reader", () => {
    expect(ariaValueText(10000, -10)).toBe("minus 10 percent, you'd have 9,000 rupees");
    expect(ariaValueText(10000, 5)).toBe("plus 5 percent, you'd have 10,500 rupees");
    expect(ariaValueText(150000, 0)).toBe("no change, you'd have 1,50,000 rupees");
  });
});

describe("the last 30 days, from the real history", () => {
  const history = [S("2026-10-01", 90), S("2026-10-14", 100), S("2026-10-20", 105), S("2026-11-13", 110)];

  it("measures the latest close against the close on or before 30 days earlier", () => {
    const change = periodChange(history, "2026-11-15T21:00:00+05:30");
    expect(change?.fromDay).toBe("2026-10-14");
    expect(change?.pct).toBeCloseTo(10, 6);
  });

  it("is left out, not estimated, when the history does not reach back 30 days", () => {
    expect(periodChange([S("2026-11-01", 100), S("2026-11-13", 110)], "2026-11-15T21:00:00+05:30")).toBeNull();
    expect(periodChange([S("2026-11-13", 110)], undefined)).toBeNull();
    expect(periodChange([], undefined)).toBeNull();
    expect(periodChange(undefined, undefined)).toBeNull();
  });

  it("leaves out a bar that is still being traded when the data was made", () => {
    const live = [S("2026-10-01", 90), S("2026-10-14", 100), S("2026-11-13", 110), S("2026-11-16", 50)];
    // made at 11:00 IST on the 16th: that day's bar is not a close yet
    expect(periodChange(live, "2026-11-16T11:00:00+05:30")?.pct).toBeCloseTo(10, 6);
  });
});
