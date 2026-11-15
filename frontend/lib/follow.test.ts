import { describe, expect, it } from "vitest";
import { parseFollow, toggled } from "@/lib/follow";
import { actionWords, peopleFromBrief, plainName } from "@/lib/people";
import type { Item } from "@/lib/types";

describe("following", () => {
  it("reads only what it expects from storage", () => {
    expect(parseFollow("{}")).toEqual({ companies: [], people: [] });
    expect(parseFollow("not json")).toEqual({ companies: [], people: [] });
    expect(parseFollow('{"companies":["HAL","HAL",3,""],"people":"x"}')).toEqual({ companies: ["HAL"], people: [] });
    expect(parseFollow('{"companies":["HAL"],"people":["INFY:Mr. A"]}')).toEqual({ companies: ["HAL"], people: ["INFY:Mr. A"] });
  });
  it("toggles an id on and off without touching the others", () => {
    expect(toggled(["A"], "B")).toEqual(["A", "B"]);
    expect(toggled(["A", "B"], "A")).toEqual(["B"]);
  });
});

function management(symbol: string, published_at: string, people: { name: string; role: string; kind: string }[]): Item {
  return {
    id: `${symbol}-${published_at}`, symbol, company: `${symbol} Ltd`, source: "bse", published_at, category: "management_change", category_label: "Management change",
    card_type: "management", priority: 50, routine: false, default_alert: true, why: "", tone: "neutral", headline: "", rule: "", subject: "", body: "", raw_category: "", raw_subcategory: "",
    url: "https://example.test/f.pdf", size_kb: 10,
    card: { type: "management", status: "ok", kind: "x", direction: "in", people: people.map((p) => ({ ...p, din: null, direction: "in" as const, effective: null, term: null, profile: null, page: 1 })), source: { url: null, pages: [] }, warnings: [], extractor: "" },
  };
}

describe("people from real filings", () => {
  it("lists each person once, newest filing first, and skips filings with no card", () => {
    const items = [
      management("HDFCBANK", "2026-11-12T10:00:00+05:30", [{ name: "Mr. V. Rangan", role: "Whole-time Director", kind: "re-appointment" }]),
      management("HDFCBANK", "2026-11-13T10:00:00+05:30", [{ name: "Mr. V. Rangan", role: "Whole-time Director", kind: "re-appointment" }]),
      management("TATASTEEL", "2026-11-07T10:00:00+05:30", [{ name: "Mr. N. Tata", role: "Director", kind: "retirement" }]),
      { ...management("INFY", "2026-11-08T10:00:00+05:30", []), card: undefined },
    ];
    const people = peopleFromBrief({ items });
    expect(people.map((p) => p.id)).toEqual(["HDFCBANK:Mr. V. Rangan", "TATASTEEL:Mr. N. Tata"]);
    expect(people[0]).toMatchObject({ action: "re-appointed", company: "HDFCBANK", filed: "2026-11-13T10:00:00+05:30" });
    expect(people[1].action).toBe("retiring");
  });
  it("words the action and drops the honorific", () => {
    expect(actionWords("resignation")).toBe("resigned");
    expect(actionWords("something_new")).toBe("something new");
    expect(plainName("Dr. Madhu Sasidhar")).toBe("Madhu Sasidhar");
    expect(plainName("Madhu")).toBe("Madhu");
  });
});
