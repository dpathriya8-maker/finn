import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applySample,
  arrowInr,
  arrowInrPct,
  clearSample,
  dayChange,
  formatInputNumber,
  formatInr,
  hasOwnEntries,
  hasSample,
  holdingLine,
  parseAmountInput,
  parseHoldings,
  parseInvested,
  parsePriceInput,
  plainPct,
  position,
  sampleHoldings,
  setHolding,
  summarize,
  totalInvested,
  type Quote,
} from "@/lib/invested";

const Q = (close: number, prevClose: number | null, changePct: number): Quote => ({ close, prevClose, changePct });

describe("the amount and price boxes", () => {
  it("read what people type", () => {
    expect(parseAmountInput("50000")).toEqual({ value: 50000, valid: true });
    expect(parseAmountInput("₹1,50,000")).toEqual({ value: 150000, valid: true });
    expect(parseAmountInput(" 2500.50 ")).toEqual({ value: 2500.5, valid: true });
    expect(parseAmountInput("0")).toEqual({ value: 0, valid: true });
    expect(parseAmountInput("")).toEqual({ value: null, valid: true });
    expect(parsePriceInput("1,234.5")).toEqual({ value: 1234.5, valid: true });
    expect(parsePriceInput("")).toEqual({ value: null, valid: true });
  });

  it("refuse anything that is not a number of rupees", () => {
    for (const bad of ["-5", "abc", "12abc", "1e5", "1.234", "99999999999999999"]) expect(parseAmountInput(bad).valid).toBe(false);
  });

  it("refuse a price of zero, below a paisa or absurdly high", () => {
    for (const bad of ["0", "0.00", "-1", "abc", "10000001"]) expect(parsePriceInput(bad).valid).toBe(false);
    expect(parsePriceInput("0.01").valid).toBe(true);
  });

  it("show Indian grouping at rest", () => {
    expect(formatInputNumber(150000)).toBe("1,50,000");
    expect(formatInputNumber(1234.5)).toBe("1,234.5");
    expect(formatInputNumber(12345678)).toBe("1,23,45,678");
  });
});

describe("stored holdings", () => {
  it("keep only well-formed symbols and sensible numbers", () => {
    expect(parseInvested('{"INFY":50000,"bad symbol":5,"TCS":-1,"ITC":"x","M&M":1200.5}')).toEqual({ INFY: 50000, "M&M": 1200.5 });
    expect(parseInvested("not json")).toEqual({});
    expect(parseInvested("[1,2]")).toEqual({});
  });

  it("read the old amounts-only format and the new one", () => {
    expect(parseHoldings('{"INFY":50000}')).toEqual({ INFY: { amount: 50000 } });
    expect(parseHoldings('{"INFY":{"amount":50000,"buyPrice":1500,"sample":true},"ITC":{"amount":-1},"LT":{"buyPrice":0}}')).toEqual({
      INFY: { amount: 50000, buyPrice: 1500, sample: true },
    });
    expect(parseHoldings('{"INFY":{"buyPrice":1500}}')).toEqual({ INFY: { buyPrice: 1500 } });
    expect(parseHoldings('{"INFY":{"sample":true}}')).toEqual({});
  });

  it("total the portfolio companies only", () => {
    expect(totalInvested({ INFY: { amount: 50000 }, ITC: { amount: 25000 }, TITAN: { amount: 9999 } }, ["INFY", "ITC", "LT"])).toBe(75000);
    expect(totalInvested({}, ["INFY"])).toBe(0);
  });
});

describe("whole rupees", () => {
  it("formats with Indian grouping", () => {
    expect(formatInr(150000)).toBe("₹1,50,000");
    expect(formatInr(775.4)).toBe("₹775");
    expect(formatInr(12345678)).toBe("₹1,23,45,678");
  });

  it("puts the arrow in the number, and nothing on zero", () => {
    expect(arrowInr(4200)).toBe("▲ ₹4,200");
    expect(arrowInr(-775.4)).toBe("▼ ₹775");
    expect(arrowInr(0)).toBe("₹0");
    expect(arrowInr(0.4)).toBe("₹0");
    expect(arrowInr(-0.4)).toBe("₹0");
  });

  it("rounds half a rupee away from zero, the same for a gain and a loss", () => {
    expect(arrowInr(2.5)).toBe("▲ ₹3");
    expect(arrowInr(-2.5)).toBe("▼ ₹3");
    expect(arrowInr(999.5)).toBe("▲ ₹1,000");
  });

  it("writes a percentage with one decimal, two when it would show 0.0", () => {
    expect(plainPct(8.4)).toBe("8.4%");
    expect(plainPct(-10.46)).toBe("10.5%");
    expect(plainPct(0.04)).toBe("0.04%");
    expect(plainPct(0)).toBe("0.0%");
    expect(arrowInrPct(4200, 8.4)).toBe("▲ ₹4,200 (8.4%)");
    expect(arrowInrPct(-775, -1.55)).toBe("▼ ₹775 (1.6%)");
    expect(arrowInrPct(0.2, 0.01)).toBe("₹0");
  });
});

describe("a position: profit, loss and today", () => {
  it("is a profit when the price is above what was paid", () => {
    // ₹50,000 at ₹100 is 500 shares; at ₹108.40 they are worth ₹54,200.
    const p = position("X", { amount: 50000, buyPrice: 100 }, Q(108.4, 107, 1.31))!;
    expect(p.shares).toBe(500);
    expect(p.value).toBeCloseTo(54200, 6);
    expect(p.pnl).toBeCloseTo(4200, 6);
    expect(p.pnlPct).toBeCloseTo(8.4, 6);
    expect(p.today).toBeCloseTo(700, 6); // 500 × (108.40 − 107)
  });

  it("is a loss when the price is below what was paid", () => {
    const p = position("X", { amount: 100000, buyPrice: 200 }, Q(150, 152, -1.3))!;
    expect(p.value).toBe(75000);
    expect(p.pnl).toBe(-25000);
    expect(p.pnlPct).toBe(-25);
    expect(p.today).toBe(-1000);
  });

  it("is exactly zero when the price equals what was paid", () => {
    const p = position("X", { amount: 12345, buyPrice: 50 }, Q(50, 50, 0))!;
    expect(p.pnl).toBe(0);
    expect(p.pnlPct).toBe(0);
    expect(p.today).toBe(0);
    expect(holdingLine(p).parts.map((x) => x.text)).toEqual(["unchanged today", "even overall"]);
  });

  it("has no profit or loss without a buy price, only today's move on the amount", () => {
    const p = position("X", { amount: 50000 }, Q(3430, 3484, -1.55))!;
    expect(p.pnl).toBeNull();
    expect(p.pnlPct).toBeNull();
    expect(p.value).toBeNull();
    expect(p.today).toBeCloseTo(-775, 6);
    expect(holdingLine(p)).toEqual({ lead: "Your ₹50,000", parts: [{ text: "▼ ₹775 today", tone: "bad" }], sample: false });
  });

  it("uses the day's change when the data has no previous close", () => {
    const p = position("X", { amount: 10000, buyPrice: 100 }, Q(110, null, 10))!;
    expect(p.today).toBeCloseTo(1100, 6); // value 11,000 × 10%
  });

  it("shows nothing it cannot know: no amount, no price", () => {
    expect(position("X", undefined, Q(100, 99, 1))).toBeNull();
    expect(position("X", { buyPrice: 100 }, Q(100, 99, 1))).toBeNull();
    const noPrice = position("X", { amount: 5000, buyPrice: 100 }, null)!;
    expect([noPrice.value, noPrice.pnl, noPrice.today]).toEqual([null, null, null]);
    expect(holdingLine(noPrice).parts).toEqual([]);
    expect(position("X", { amount: 5000, buyPrice: 100 }, Q(0, 0, 0))!.pnl).toBeNull();
  });

  it("says both lines the way the Brief shows them", () => {
    const p = position("X", { amount: 50000, buyPrice: 100 }, Q(108.4, 107, 1.31))!;
    expect(holdingLine(p)).toEqual({
      lead: "Your ₹50,000",
      parts: [
        { text: "▲ ₹700 today", tone: "good" },
        { text: "▲ ₹4,200 overall", tone: "good" },
      ],
      sample: false,
    });
  });

  it("keeps the arithmetic exact for huge amounts", () => {
    const p = position("X", { amount: 1_000_000_000_000, buyPrice: 100 }, Q(150, 149, 0.67))!; // ₹1 lakh crore
    expect(p.value).toBe(1_500_000_000_000);
    expect(p.pnl).toBe(500_000_000_000);
    expect(p.pnlPct).toBe(50);
    expect(arrowInr(p.pnl!)).toBe("▲ ₹5,00,00,00,00,000");
    expect(formatInr(p.value!)).toBe("₹15,00,00,00,00,000");
  });

  it("copes with a very small buy price and a tiny amount", () => {
    const p = position("X", { amount: 1, buyPrice: 0.01 }, Q(0.02, 0.01, 100))!;
    expect(p.shares).toBeCloseTo(100, 9);
    expect(p.pnl).toBeCloseTo(1, 9);
    expect(arrowInr(p.pnl!)).toBe("▲ ₹1");
  });

  it("rounds only when it shows, so a sum of small amounts is not off by a rupee", () => {
    const quote = Q(100.4, 100, 0.4);
    const holdings = { A: { amount: 1000, buyPrice: 100 }, B: { amount: 1000, buyPrice: 100 }, C: { amount: 1000, buyPrice: 100 } };
    const s = summarize(holdings, ["A", "B", "C"], () => quote)!;
    expect(s.overall).toBeCloseTo(12, 6); // each is +₹4 exactly; rounding each first would also give 12, rounding 3.5s would not
    const half = summarize({ A: { amount: 1000, buyPrice: 100 }, B: { amount: 1000, buyPrice: 100 } }, ["A", "B"], () => Q(100.35, 100, 0.35))!;
    expect(half.overall).toBeCloseTo(7, 6); // 3.5 + 3.5: shown as ₹7, not ₹8 (4 + 4)
    expect(arrowInr(half.overall!)).toBe("▲ ₹7");
  });
});

describe("the portfolio summary", () => {
  const quotes: Record<string, Quote> = {
    UP: Q(120, 118, 1.69), // bought at 100: +20%
    DOWN: Q(80, 82, -2.44), // bought at 100: −20%
    FLAT: Q(50, 50, 0),
    NOPRICE: Q(500, 495, 1.01), // no buy price
  };
  const quoteOf = (symbol: string) => quotes[symbol] ?? null;

  it("is null until an amount is set", () => {
    expect(summarize({}, ["UP"], quoteOf)).toBeNull();
    expect(summarize({ UP: { buyPrice: 100 } }, ["UP"], quoteOf)).toBeNull();
  });

  it("adds up invested, worth, overall and today, and orders the biggest loss first", () => {
    const holdings = { UP: { amount: 10000, buyPrice: 100 }, DOWN: { amount: 30000, buyPrice: 100 }, FLAT: { amount: 5000, buyPrice: 50 } };
    const s = summarize(holdings, ["UP", "DOWN", "FLAT"], quoteOf)!;
    expect(s.invested).toBe(45000);
    expect(s.value).toBeCloseTo(12000 + 24000 + 5000, 6);
    expect(s.overall).toBeCloseTo(2000 - 6000, 6);
    expect(s.overallPct).toBeCloseTo((-4000 / 45000) * 100, 6);
    expect(s.today).toBeCloseTo(100 * 2 + 300 * -2 + 0, 6); // UP: 100 shares × ₹2, DOWN: 300 shares × −₹2
    expect(s.rows.map((r) => r.symbol)).toEqual(["DOWN", "FLAT", "UP"]);
    expect(s.weightBasis).toBe("value");
    expect(s.rows.reduce((sum, r) => sum + r.weight, 0)).toBeCloseTo(100, 6);
  });

  it("counts only holdings with a buy price in value and overall, and says how many", () => {
    const holdings = { UP: { amount: 10000, buyPrice: 100 }, NOPRICE: { amount: 20000 } };
    const s = summarize(holdings, ["UP", "NOPRICE"], quoteOf)!;
    expect(s.count).toBe(2);
    expect(s.priced).toBe(1);
    expect(s.invested).toBe(30000);
    expect(s.pricedInvested).toBe(10000);
    expect(s.value).toBeCloseTo(12000, 6);
    expect(s.overall).toBeCloseTo(2000, 6);
    expect(s.overallPct).toBeCloseTo(20, 6);
    expect(s.today).toBeCloseTo(200 + (20000 * 1.01) / 100, 6);
    expect(s.weightBasis).toBe("invested");
    expect(s.rows.map((r) => r.symbol)).toEqual(["UP", "NOPRICE"]); // priced first, then the rest
  });

  it("has no value or overall when nobody has a buy price", () => {
    const s = summarize({ NOPRICE: { amount: 20000 } }, ["NOPRICE"], quoteOf)!;
    expect([s.value, s.overall, s.overallPct]).toEqual([null, null, null]);
    expect(s.today).toBeCloseTo(202, 6);
  });

  it("ignores companies that are not in the portfolio list", () => {
    expect(summarize({ UP: { amount: 10000, buyPrice: 100 } }, ["DOWN"], quoteOf)).toBeNull();
  });
});

describe("sample holdings", () => {
  it("are fixed amounts on the first six companies that have a price, with a buy price near the close", () => {
    const companies = [
      { symbol: "A", close: 1000 },
      { symbol: "B", close: null },
      ...["C", "D", "E", "F", "G", "H"].map((symbol) => ({ symbol, close: 200 })),
    ];
    const s = sampleHoldings(companies);
    expect(Object.keys(s)).toEqual(["A", "C", "D", "E", "F", "G"]);
    expect(s.A).toEqual({ amount: 50000, buyPrice: 860, sample: true });
    expect(s.C.amount).toBe(25000);
    expect(Object.values(s).every((h) => h.sample)).toBe(true);
    const gains = Object.values(s).filter((h) => h.buyPrice! < (h === s.A ? 1000 : 200)).length;
    expect(gains).toBeGreaterThan(0);
    expect(gains).toBeLessThan(6); // a mix, so both colours are shown
  });
});

describe("the store (a stand-in for localStorage)", () => {
  const data = new Map<string, string>();
  beforeEach(() => {
    data.clear();
    vi.stubGlobal("window", {
      localStorage: { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) },
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    });
  });
  afterEach(() => vi.unstubAllGlobals());
  const stored = () => parseHoldings(data.get("finn.holdings.v2") ?? "{}");

  it("saves an amount and a buy price separately, and clears them", () => {
    setHolding("INFY", { amount: 50000 });
    setHolding("INFY", { buyPrice: 1500 });
    expect(stored()).toEqual({ INFY: { amount: 50000, buyPrice: 1500 } });
    setHolding("INFY", { buyPrice: null });
    expect(stored()).toEqual({ INFY: { amount: 50000 } });
    setHolding("INFY", { amount: null });
    expect(stored()).toEqual({});
  });

  it("reads the first version's amounts-only key", () => {
    data.set("finn.invested.v1", '{"ITC":25000}');
    setHolding("INFY", { buyPrice: 1500 }); // the first write moves everything to the new key
    expect(stored()).toEqual({ ITC: { amount: 25000 }, INFY: { buyPrice: 1500 } });
  });

  it("marks a sample, tells a sample from the reader's own, and clears only the sample", () => {
    setHolding("ITC", { amount: 25000 });
    expect(hasOwnEntries(stored())).toBe(true);
    expect(hasSample(stored())).toBe(false);
    applySample({ INFY: { amount: 50000, buyPrice: 1300 }, LT: { amount: 10000, buyPrice: 3000 } });
    expect(stored()).toEqual({ INFY: { amount: 50000, buyPrice: 1300, sample: true }, LT: { amount: 10000, buyPrice: 3000, sample: true } });
    expect(hasSample(stored())).toBe(true);
    expect(hasOwnEntries(stored())).toBe(false);
    setHolding("ITC", { amount: 777 }); // the reader types their own
    clearSample();
    expect(stored()).toEqual({ ITC: { amount: 777 } });
  });

  it("makes a sample entry the reader's own when they edit it, without keeping the invented half", () => {
    applySample({ INFY: { amount: 50000, buyPrice: 1300 } });
    setHolding("INFY", { amount: 60000 });
    expect(stored()).toEqual({ INFY: { amount: 60000 } });
  });

  it("does not break when storage is not there", () => {
    vi.stubGlobal("window", { localStorage: { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } }, addEventListener: () => undefined, removeEventListener: () => undefined });
    expect(() => setHolding("INFY", { amount: 1 })).not.toThrow();
  });
});

describe("what a day's move means in rupees", () => {
  it("is the amount times the day's change", () => {
    expect(dayChange(50000, -1.55)).toBeCloseTo(-775, 6);
    expect(dayChange(10000, 4.2)).toBeCloseTo(420, 6);
  });
});
