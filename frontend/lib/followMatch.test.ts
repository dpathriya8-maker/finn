import { describe, expect, it } from "vitest";
import { parseFollow, toggled, type Follow } from "@/lib/follow";
import { becauseLine, isFollowed, isFullName, mergeBriefs, namedPeople, nameInText, nothingLine, reasonsFor, suggest, topicMatches, TOPICS } from "@/lib/followMatch";
import { groupItems, selectItems } from "@/lib/brief";
import { peopleFromBrief } from "@/lib/people";
import type { Brief, Item } from "@/lib/types";

function item(over: Partial<Item> & { id: string }): Item {
  return {
    symbol: "KAYNES", company: "Kaynes Technology India Ltd", source: "bse", published_at: "2026-11-15T10:00:00+05:30", category: "press_release", category_label: "Press release",
    card_type: "one_liner", priority: 50, routine: false, default_alert: false, why: "", tone: "neutral", headline: "Update", rule: "", subject: "", body: "", raw_category: "", raw_subcategory: "",
    url: null, size_kb: null, ...over,
  };
}

const none: Follow = { companies: [], people: [], topics: [] };
const label = (symbol: string) => (symbol === "KAYNES" ? "Kaynes Technology" : symbol);

describe("a person is matched by their exact full name", () => {
  it("ignores case and the honorific, and needs whole words", () => {
    expect(nameInText("V. Srinivasa Rangan", "Re-appointment of Mr. V. Srinivasa Rangan as Whole-time Director")).toBe(true);
    expect(nameInText("v. srinivasa rangan", "MR. V. SRINIVASA RANGAN was appointed")).toBe(true);
    expect(nameInText("Leo Puri", "Mr. Leo  Puri\nhas resigned")).toBe(true); // any run of spaces or line breaks
    expect(nameInText("Leo Puri", "Mr. Leo Purington has resigned")).toBe(false);
    expect(nameInText("Leo Puri", "Mr. Aleo Puri has resigned")).toBe(false);
    expect(nameInText("Leo Puri", "Leo Puri.")).toBe(true);
    expect(nameInText("Leo Puri", "(Leo Puri)")).toBe(true);
  });

  it("never matches on one word, so a surname cannot catch half the filings", () => {
    expect(isFullName("Tata")).toBe(false);
    expect(isFullName("Leo Puri")).toBe(true);
    expect(isFullName("V. Rangan")).toBe(true);
    expect(nameInText("Tata", "Tata Steel Limited")).toBe(false);
  });

  it("treats a name written with regex characters as plain text", () => {
    expect(nameInText("A. B. (C) Rao", "Mr. A. B. (C) Rao")).toBe(true);
    expect(nameInText(".* .*", "anything at all")).toBe(false);
  });
});

describe("a topic is matched by category, or by keywords in the headline or subject", () => {
  it("has the ten topics", () => {
    expect(TOPICS.map((t) => t.label)).toEqual(["Results", "Dividend", "Fund raise", "M&A", "Management change", "Credit rating", "Orders & contracts", "Capex", "Legal", "Pledging"]);
  });
  it("matches by category", () => {
    expect(topicMatches({ category: "results", headline: "x", subject: "y" }, "results")).toBe(true);
    expect(topicMatches({ category: "litigation", headline: "x", subject: "y" }, "legal")).toBe(true);
    expect(topicMatches({ category: "management_change", headline: "x", subject: "y" }, "management_change")).toBe(true);
    expect(topicMatches({ category: "results", headline: "x", subject: "y" }, "dividend")).toBe(false);
  });
  it("matches an order win that was filed as a plain update", () => {
    expect(topicMatches({ category: "press_release", headline: "Bagging/receiving of order(s) or contract(s)", subject: "" }, "orders")).toBe(true);
    expect(topicMatches({ category: "press_release", headline: "Update", subject: "Company secures an order worth Rs 500 crore" }, "orders")).toBe(true);
    expect(topicMatches({ category: "press_release", headline: "Newspaper publication", subject: "Notice of the board meeting" }, "orders")).toBe(false);
  });
  it("matches a rating or a dividend named only in the words", () => {
    expect(topicMatches({ category: "unclassified", headline: "Announcement as attached", subject: "CRISIL reaffirms rating" }, "credit_rating")).toBe(true);
    expect(topicMatches({ category: "unclassified", headline: "Interim dividend of Rs 2", subject: "" }, "dividend")).toBe(true);
  });
  it("does not know a topic it was not given", () => {
    expect(topicMatches({ category: "results", headline: "x", subject: "y" }, "nonsense")).toBe(false);
  });
});

describe("why a filing is in the Following feed", () => {
  const kaynes = item({ id: "a", headline: "Q2 FY27 results", category: "results" });
  it("matches a company by its symbol, and only that", () => {
    expect(reasonsFor(kaynes, { ...none, companies: ["KAYNES"] }, label).map((r) => r.label)).toEqual(["Kaynes Technology"]);
    expect(reasonsFor(kaynes, { ...none, companies: ["LT"] }, label)).toEqual([]);
  });
  it("matches a person named in the headline, subject or body, or on the card", () => {
    const f = { ...none, people: ["Leo Puri"] };
    expect(reasonsFor(item({ id: "b", symbol: "ASIANPAINT", headline: "Appointment of Mr. Leo Puri" }), f, label)).toHaveLength(1);
    expect(reasonsFor(item({ id: "c", subject: "x", body: "The Board noted the resignation of Leo Puri." }), f, label)).toHaveLength(1);
    const card = { type: "management" as const, status: "ok" as const, kind: "resignation", direction: "out" as const, source: { url: null, pages: [] }, warnings: [], extractor: "",
      people: [{ name: "Mr. Leo Puri", din: null, role: "Director", kind: "resignation", direction: "out" as const, effective: null, term: null, profile: null, page: 1 }] };
    expect(reasonsFor(item({ id: "d", card }), f, label)).toHaveLength(1);
    expect(reasonsFor(item({ id: "e", body: "Leo Purington" }), f, label)).toEqual([]);
  });
  it("matches a topic, and lists every reason once, companies first", () => {
    const reasons = reasonsFor(kaynes, { companies: ["KAYNES"], people: [], topics: ["results", "dividend"] }, label);
    expect(reasons.map((r) => `${r.kind}:${r.label}`)).toEqual(["company:Kaynes Technology", "topic:Results"]);
  });
  it("says it in a grey line, naming at most three", () => {
    expect(becauseLine([{ kind: "company", id: "KAYNES", label: "Kaynes Technology" }, { kind: "topic", id: "results", label: "Results" }])).toBe("Because you follow Kaynes Technology, Results");
    const four = ["A", "B", "C", "D"].map((l) => ({ kind: "topic" as const, id: l, label: l }));
    expect(becauseLine(four)).toBe("Because you follow A, B, C and 1 more");
    expect(becauseLine([])).toBe("");
  });
  it("matches nothing when nothing is followed", () => {
    expect(reasonsFor(kaynes, none, label)).toEqual([]);
  });
});

describe("the feed itself", () => {
  const mk = (over: Partial<Brief> = {}): Brief => ({ schema: 1, generated_at: "2026-11-16T04:34:00+05:30", item_days: 14, companies: [], items: [], signals: [], ...over });
  it("joins the two briefs, each filing and company once, with the later time", () => {
    const a = mk({ generated_at: "2026-11-15T21:00:00+05:30", items: [item({ id: "1" }), item({ id: "2" })], companies: [{ symbol: "KAYNES", name: "K", sector: "", size_bucket: "", stale: {}, errors: {} }], signals: [{ symbol: "KAYNES", sessions: [] }] });
    const b = mk({ items: [item({ id: "2" }), item({ id: "3", symbol: "HAL" })], companies: [{ symbol: "HAL", name: "H", sector: "", size_bucket: "", stale: {}, errors: {} }], signals: [{ symbol: "HAL", sessions: [] }] });
    const merged = mergeBriefs(a, b, null)!;
    expect(merged.items.map((i) => i.id)).toEqual(["1", "2", "3"]);
    expect(merged.companies.map((c) => c.symbol)).toEqual(["KAYNES", "HAL"]);
    expect(merged.signals).toHaveLength(2);
    expect(merged.generated_at).toBe("2026-11-16T04:34:00+05:30");
    expect(mergeBriefs(null, undefined)).toBeNull();
  });

  it("counts the window back from the data's own time, and puts the risk first, without a duplicate", () => {
    const items = [
      item({ id: "ok", symbol: "KAYNES", priority: 40, published_at: "2026-11-15T12:00:00+05:30" }),
      item({ id: "risk", symbol: "KAYNES", priority: 90, tone: "bad", category: "results", published_at: "2026-11-15T11:00:00+05:30" }),
      item({ id: "old", symbol: "KAYNES", priority: 99, published_at: "2026-11-01T11:00:00+05:30" }),
      item({ id: "other", symbol: "LT", priority: 99, published_at: "2026-11-15T11:00:00+05:30" }),
    ];
    const follow = { companies: ["KAYNES"], people: [], topics: ["results"] }; // "risk" matches the company and the topic
    const brief = mk({ items });
    const matched = selectItems(brief, 168).filter((i) => reasonsFor(i, follow, label).length > 0);
    expect(matched.map((i) => i.id).sort()).toEqual(["ok", "risk"]);
    expect(groupItems(matched).high.map((i) => i.id)).toEqual(["risk"]);
  });
});

describe("people named in the filings", () => {
  const card = (name: string) => ({ type: "management" as const, status: "ok" as const, kind: "appointment", direction: "in" as const, source: { url: null, pages: [] }, warnings: [], extractor: "",
    people: [{ name, din: null, role: "Director", kind: "appointment", direction: "in" as const, effective: null, term: null, profile: null, page: 1 }] });
  it("takes them from management cards and from honorifics, without the honorific, once each", () => {
    const items = [
      item({ id: "1", symbol: "HDFCBANK", company: "HDFC Bank Ltd", published_at: "2026-11-13T10:00:00+05:30", headline: "Re-appointment of Mr. V. Srinivasa Rangan as Whole-time Director", card: card("Mr. V. Srinivasa Rangan") }),
      item({ id: "2", symbol: "HDFCBANK", company: "HDFC Bank Ltd", published_at: "2026-11-12T10:00:00+05:30", subject: "Mr. V. Srinivasa Rangan to retire" }),
      item({ id: "3", symbol: "APOLLOHOSP", company: "Apollo Hospitals Enterprise Ltd", published_at: "2026-11-04T10:00:00+05:30", body: "Dr. Madhu Sasidhar, Independent Director, was appointed." }),
      item({ id: "4", symbol: "ASIANPAINT", company: "Asian Paints Ltd", published_at: "2026-11-06T10:00:00+05:30", headline: "Mr. Leo Puri Independent Director" }),
    ];
    const people = namedPeople(items);
    expect(people.map((p) => p.name)).toEqual(["V. Srinivasa Rangan", "Leo Puri", "Madhu Sasidhar"]);
    expect(people[0]).toMatchObject({ symbol: "HDFCBANK", company: "HDFC Bank" });
  });
  it("skips a lone first name or a word that is not a name", () => {
    expect(namedPeople([item({ id: "1", body: "Mr. Chairman will speak. Dr. Reddy." })])).toEqual([]);
  });
  it("gives a followed person's name without the honorific", () => {
    const [p] = peopleFromBrief({ items: [item({ id: "1", card: card("Mr. V. Rangan") })] });
    expect(p.followName).toBe("V. Rangan");
  });
});

describe("the search box", () => {
  const universe = {
    companies: [
      { symbol: "KAYNES", name: "Kaynes Technology India Ltd" },
      { symbol: "BAJFINANCE", name: "Bajaj Finance Ltd" },
      { symbol: "HDFCBANK", name: "HDFC Bank Ltd" },
    ],
    people: [{ name: "Leo Puri", company: "Asian Paints", symbol: "ASIANPAINT" }],
  };
  it("offers nothing for an empty box", () => {
    expect(suggest("", universe)).toEqual([]);
    expect(suggest("   ", universe)).toEqual([]);
  });
  it("finds a company by name or symbol, a person by name, a topic by label", () => {
    expect(suggest("kay", universe)[0]).toMatchObject({ kind: "company", id: "KAYNES", label: "Kaynes Technology India" });
    expect(suggest("bajfin", universe)[0]).toMatchObject({ kind: "company", id: "BAJFINANCE" });
    expect(suggest("leo", universe)[0]).toMatchObject({ kind: "person", id: "Leo Puri" });
    expect(suggest("divid", universe)[0]).toMatchObject({ kind: "topic", id: "dividend" });
    expect(suggest("orders", universe)[0]).toMatchObject({ kind: "topic", id: "orders" });
    expect(suggest("m&a", universe)[0]).toMatchObject({ kind: "topic", id: "m_and_a" });
  });
  it("offers to follow a typed full name that is not listed, and not a single word", () => {
    expect(suggest("Ravi Kumar", universe).at(-1)).toMatchObject({ kind: "typed", id: "Ravi Kumar" });
    expect(suggest("Ravi", universe).some((s) => s.kind === "typed")).toBe(false);
    expect(suggest("Leo Puri", universe).some((s) => s.kind === "typed")).toBe(false); // already listed
    expect(suggest("123 456", universe).some((s) => s.kind === "typed")).toBe(false);
  });
  it("knows what is already followed", () => {
    const f = { companies: ["KAYNES"], people: ["Leo Puri"], topics: ["results"] };
    expect(isFollowed(f, "company", "KAYNES")).toBe(true);
    expect(isFollowed(f, "person", "leo puri")).toBe(true);
    expect(isFollowed(f, "typed", "Leo Puri")).toBe(true);
    expect(isFollowed(f, "topic", "dividend")).toBe(false);
  });
});

describe("empty states and storage", () => {
  it("says there are no filings, in the window's own words", () => {
    expect(nothingLine("Kaynes Technology", "7 days")).toBe("No filings about Kaynes Technology in the last 7 days.");
  });
  it("reads the old people format and the new topics", () => {
    expect(parseFollow('{"companies":["HAL"],"people":["INFY:Mr. Rahul Rao","Dr. Madhu Sasidhar","madhu sasidhar"],"topics":["results",3]}')).toEqual({
      companies: ["HAL"],
      people: ["Rahul Rao", "Madhu Sasidhar"],
      topics: ["results"],
    });
    expect(parseFollow("{}")).toEqual({ companies: [], people: [], topics: [] });
    expect(parseFollow("not json")).toEqual({ companies: [], people: [], topics: [] });
  });
  it("toggles without regard to case, and leaves the others", () => {
    expect(toggled(["Leo Puri"], "leo puri")).toEqual([]);
    expect(toggled(["A"], "B")).toEqual(["A", "B"]);
  });
});
