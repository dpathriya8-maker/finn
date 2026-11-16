import { describe, expect, it } from "vitest";
import { parseOverrides, resolveSettings } from "@/lib/settings";
import type { AppConfig } from "@/lib/types";

const config: AppConfig = {
  schema: 1,
  defaults: { window_hours: 24, volume_multiple: 2, price_move_pct: 5, volume_lookback_days: 20 },
  categories: [
    { id: "results", label: "Results", why: "", weight: 88, is_routine: false, default_alert: true, card_type: "results" },
    { id: "dividend", label: "Dividend", why: "", weight: 50, is_routine: false, default_alert: false, card_type: "one_liner" },
  ],
};

describe("parseOverrides", () => {
  it("accepts well-formed values", () => {
    expect(parseOverrides('{"windowHours":72,"volumeMultiple":3,"priceMovePct":7.5,"mutedSymbols":["ITC"],"alertCategories":{"dividend":true}}')).toEqual({
      windowHours: 72, volumeMultiple: 3, priceMovePct: 7.5, mutedSymbols: ["ITC"], alertCategories: { dividend: true },
    });
  });

  it("ignores anything that is not valid JSON or not an object", () => {
    expect(parseOverrides("not json")).toEqual({});
    expect(parseOverrides("[1,2]")).toEqual({});
    expect(parseOverrides("null")).toEqual({});
    expect(parseOverrides('"a string"')).toEqual({});
  });

  it("drops numbers that are out of range or of the wrong type instead of trusting them", () => {
    expect(parseOverrides('{"windowHours":999999,"volumeMultiple":-1,"priceMovePct":"5"}')).toEqual({});
    expect(parseOverrides('{"windowHours":0}')).toEqual({});
  });

  it("keeps only strings in the muted list and only booleans in the category map", () => {
    expect(parseOverrides('{"mutedSymbols":["ITC",5,null],"alertCategories":{"a":true,"b":"yes","c":false}}')).toEqual({
      mutedSymbols: ["ITC"], alertCategories: { a: true, c: false },
    });
  });
});

describe("resolveSettings", () => {
  it("follows the published defaults when the user changed nothing", () => {
    expect(resolveSettings({}, config)).toEqual({
      windowHours: 24, windowChosen: false, volumeMultiple: 2, priceMovePct: 5, mutedSymbols: [],
      alertCategories: { results: true, dividend: false },
    });
  });

  it("lets the user's choices win over the defaults", () => {
    const s = resolveSettings({ windowHours: 168, volumeMultiple: 3, alertCategories: { dividend: true, results: false }, mutedSymbols: ["ITC"] }, config);
    expect(s.windowHours).toBe(168);
    expect(s.windowChosen).toBe(true);
    expect(s.volumeMultiple).toBe(3);
    expect(s.alertCategories).toEqual({ results: false, dividend: true });
    expect(s.mutedSymbols).toEqual(["ITC"]);
  });

  it("works before the config has loaded, on the built-in smart defaults", () => {
    expect(resolveSettings({}, null)).toMatchObject({ windowHours: 24, volumeMultiple: 2, priceMovePct: 5, alertCategories: {} });
  });
});
