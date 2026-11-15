import { describe, expect, it } from "vitest";
import { dayChange, formatInr, holdingLine, parseAmountInput, parseInvested, totalInvested } from "@/lib/invested";

describe("the amount box", () => {
  it("reads what people type", () => {
    expect(parseAmountInput("50000")).toEqual({ value: 50000, valid: true });
    expect(parseAmountInput("₹1,50,000")).toEqual({ value: 150000, valid: true });
    expect(parseAmountInput(" 2500.50 ")).toEqual({ value: 2500.5, valid: true });
    expect(parseAmountInput("0")).toEqual({ value: 0, valid: true });
    expect(parseAmountInput("")).toEqual({ value: null, valid: true });
  });

  it("refuses anything that is not a number of rupees, 0 or more", () => {
    for (const bad of ["-5", "abc", "12abc", "1e5", "1.234", "99999999999999999"]) expect(parseAmountInput(bad).valid).toBe(false);
  });
});

describe("stored amounts", () => {
  it("keeps only well-formed symbols and positive numbers", () => {
    expect(parseInvested('{"INFY":50000,"bad symbol":5,"TCS":-1,"ITC":"x","M&M":1200.5}')).toEqual({ INFY: 50000, "M&M": 1200.5 });
    expect(parseInvested("not json")).toEqual({});
    expect(parseInvested("[1,2]")).toEqual({});
  });

  it("totals the portfolio companies only", () => {
    expect(totalInvested({ INFY: 50000, ITC: 25000, TITAN: 9999 }, ["INFY", "ITC", "LT"])).toBe(75000);
    expect(totalInvested({}, ["INFY"])).toBe(0);
  });
});

describe("what a day's move means in rupees", () => {
  it("formats with Indian grouping", () => {
    expect(formatInr(150000)).toBe("₹1,50,000");
    expect(formatInr(775.4)).toBe("₹775");
    expect(formatInr(12345678)).toBe("₹1,23,45,678");
  });

  it("is the amount times the day's change", () => {
    expect(dayChange(50000, -1.55)).toBeCloseTo(-775, 6);
    expect(dayChange(10000, 4.2)).toBeCloseTo(420, 6);
  });

  it("says it with an arrow and a colour, or says unchanged", () => {
    expect(holdingLine(50000, -1.55)).toEqual({ lead: "Your ₹50,000 · ", move: "▼ ₹775 today", tone: "bad" });
    expect(holdingLine(50000, 0.5)).toEqual({ lead: "Your ₹50,000 · ", move: "▲ ₹250 today", tone: "good" });
    expect(holdingLine(100, 0.1)).toEqual({ lead: "Your ₹100 · ", move: "unchanged today", tone: "flat" });
  });
});
