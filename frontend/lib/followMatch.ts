import type { Follow } from "@/lib/follow";
import { shortName } from "@/lib/headline";
import { plainName } from "@/lib/people";
import type { Brief, Item } from "@/lib/types";

/**
 * What a followed company, person or topic means, as rules over filings (never a model, never news):
 *   a company matches by symbol;
 *   a person matches by their exact full name, case-insensitive and as whole words, in a filing's headline, subject or body
 *   (and in the names a management-change card read out of the filing);
 *   a topic matches by the filing's category, or by a keyword in its headline or subject.
 * Everything here is pure so it can be tested without a browser.
 */
export type Topic = { id: string; label: string; categories: string[]; keywords: RegExp[] };

/** The ten topics. Categories come from config/categories.json; keywords catch what a category does not (an order win is filed as an update). */
export const TOPICS: readonly Topic[] = [
  { id: "results", label: "Results", categories: ["results"], keywords: [/\bfinancial results\b/i] },
  { id: "dividend", label: "Dividend", categories: ["dividend"], keywords: [/\bdividend\b/i] },
  {
    id: "fund_raise",
    label: "Fund raise",
    categories: ["fund_raise"],
    keywords: [/\bfund[- ]?raising\b/i, /\bqip\b/i, /\brights issue\b/i, /\bpreferential (?:issue|allotment)\b/i, /\bncds?\b/i],
  },
  {
    id: "m_and_a",
    label: "M&A",
    categories: ["m_and_a"],
    keywords: [/\bacquisitions?\b/i, /\bmerger\b/i, /\bamalgamation\b/i, /\bdemerger\b/i, /\btakeover\b/i, /\bjoint venture\b/i, /\bslump sale\b/i],
  },
  { id: "management_change", label: "Management change", categories: ["management_change"], keywords: [] },
  {
    id: "credit_rating",
    label: "Credit rating",
    categories: ["credit_rating"],
    keywords: [/\bcredit rating\b/i, /\bre-?affirmation of rating\b/i, /\b(?:crisil|icra|care ratings|moody'?s|fitch|s&p global ratings)\b/i],
  },
  {
    id: "orders",
    label: "Orders & contracts",
    categories: [],
    keywords: [
      /\bbagging\b/i,
      /\b(?:receiving|receipt) of orders?\b/i,
      /\border (?:wins?|inflows?)\b/i,
      /\b(?:new|large|major|significant) orders?\b/i,
      /\bletters? of (?:award|intent)\b/i,
      /\b(?:wins?|won|awarded|secures?|secured|bags?|bagged) (?:an? |the )?(?:\w+ ){0,3}(?:orders?|contracts?)\b/i,
    ],
  },
  { id: "capex", label: "Capex", categories: ["capex"], keywords: [/\bcapex\b/i, /\bcapital expenditure\b/i, /\bcapacity expansion\b/i, /\b(?:greenfield|brownfield)\b/i] },
  {
    id: "legal",
    label: "Legal",
    categories: ["litigation"],
    keywords: [/\blitigation\b/i, /\b(?:high|supreme) court\b/i, /\btribunal\b/i, /\bshow[- ]cause\b/i, /\bnclt\b/i, /\bpenalt(?:y|ies)\b/i],
  },
  { id: "pledging", label: "Pledging", categories: ["pledging"], keywords: [/\bpledg(?:e|ed|ing)\b/i, /\bencumbrance\b/i] },
];

export function topicById(id: string): Topic | undefined {
  return TOPICS.find((t) => t.id === id);
}

/** A topic matches a filing by its category, or by a keyword in its headline or subject (the body is too long to trust for keywords). */
export function topicMatches(item: Pick<Item, "category" | "headline" | "subject">, topicId: string): boolean {
  const topic = topicById(topicId);
  if (!topic) return false;
  if (topic.categories.includes(item.category)) return true;
  const text = `${item.headline} ${item.subject}`;
  return topic.keywords.some((k) => k.test(text));
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** At least two words, so a first name or a surname alone can never match half the filings. */
export function isFullName(name: string): boolean {
  const words = name.trim().split(/\s+/).filter((w) => /\p{L}{2,}|\p{L}\./u.test(w));
  return words.length >= 2 && name.trim().length >= 5;
}

/** The exact full name, case-insensitive, as whole words: "V. Srinivasa Rangan" is in "Mr. V. Srinivasa Rangan was re-appointed", not in "Srinivasa Rangana". */
export function nameInText(name: string, text: string): boolean {
  const clean = name.trim().replace(/\s+/g, " ");
  if (!isFullName(clean)) return false;
  const pattern = escapeRegExp(clean).replace(/ /g, "\\s+");
  return new RegExp(`(?<![\\p{L}\\p{N}])${pattern}(?![\\p{L}\\p{N}])`, "iu").test(text);
}

/** The words of a filing a name is looked for in: headline, subject, body, and the names the management card read from the filing itself. */
export function itemText(item: Item): string {
  const names = item.card && item.card.type === "management" && item.card.status !== "failed" ? item.card.people.map((p) => p.name).join(" ") : "";
  return `${item.headline} ${item.subject} ${item.body} ${names}`;
}

export type Reason = { kind: "company" | "person" | "topic"; id: string; label: string };

/** Why a filing is in the Following feed: every followed company, person and topic it matches, companies first. Empty if none. */
export function reasonsFor(item: Item, follow: Follow, companyLabel: (symbol: string) => string): Reason[] {
  const reasons: Reason[] = [];
  if (follow.companies.includes(item.symbol)) reasons.push({ kind: "company", id: item.symbol, label: companyLabel(item.symbol) });
  if (follow.people.length > 0) {
    const text = itemText(item);
    for (const person of follow.people) if (nameInText(person, text)) reasons.push({ kind: "person", id: person, label: person });
  }
  for (const id of follow.topics) {
    const topic = topicById(id);
    if (topic && topicMatches(item, id)) reasons.push({ kind: "topic", id, label: topic.label });
  }
  return reasons;
}

/** "Because you follow Kaynes Technology, Results" (at most three reasons named, then "and 2 more"). */
export function becauseLine(reasons: readonly Reason[]): string {
  if (reasons.length === 0) return "";
  const names = reasons.slice(0, 3).map((r) => r.label);
  const more = reasons.length - names.length;
  return `Because you follow ${names.join(", ")}${more > 0 ? ` and ${more} more` : ""}`;
}

/** The two briefs as one, for matching and for prices: filings once each (by id), every company, the later of the two times. */
export function mergeBriefs(...briefs: (Brief | null | undefined)[]): Brief | null {
  const parts = briefs.filter((b): b is Brief => !!b);
  if (parts.length === 0) return null;
  const once = <T,>(list: T[], key: (x: T) => string): T[] => {
    const seen = new Set<string>();
    return list.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  };
  const latest = parts.map((b) => b.generated_at).sort((x, y) => Date.parse(y) - Date.parse(x))[0];
  return {
    schema: parts[0].schema,
    generated_at: latest,
    item_days: Math.min(...parts.map((b) => b.item_days)),
    companies: once(parts.flatMap((b) => b.companies), (c) => c.symbol),
    items: once(parts.flatMap((b) => b.items), (i) => i.id),
    signals: once(parts.flatMap((b) => b.signals), (s) => s.symbol),
  };
}

// -------------------------------------------------------------------------------------------------------------- people in filings
const HONORIFIC = /\b(?:Mr|Mrs|Ms|Dr|Shri|Smt|Prof|CA|CS)\.?\s+((?:[A-Z][A-Za-z'’-]*\.?)(?:\s+[A-Z][A-Za-z'’-]*\.?){1,3})/g;
// Words that follow a name in a filing's sentence and are not part of it.
const NOT_NAME = new Set(["As", "Of", "And", "Director", "Independent", "Executive", "Non", "Non-Executive", "Chairman", "Managing", "Whole", "Whole-time", "Time", "Additional", "Officer", "Chief", "Company", "Limited", "Ltd", "The", "To", "In", "For", "On", "Is", "Has", "Have", "Be", "By", "With"]);

/** A name trimmed of the words after it that are not part of it, or null if fewer than two words are left. */
function cleanName(raw: string): string | null {
  const words = raw.replace(/\s+/g, " ").trim().split(" ");
  const kept: string[] = [];
  for (const word of words) {
    if (NOT_NAME.has(word.replace(/[,.;:]$/, ""))) break;
    kept.push(word.replace(/[,;:]$/, ""));
  }
  const name = kept.join(" ").replace(/\.$/, kept[kept.length - 1].length <= 2 ? "." : "");
  return isFullName(name) ? name : null;
}

export type NamedPerson = { name: string; company: string; symbol: string };

/**
 * People named in the filings: from the management-change cards (the filing's own list of who comes and goes) and, by the same
 * kind of rule, anyone written with an honorific ("Dr. Madhu Sasidhar") in a headline, subject or body. Each name once, without its
 * honorific, newest filing first. A suggestion, never a claim about the person.
 */
export function namedPeople(items: readonly Item[]): NamedPerson[] {
  const sorted = [...items].sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at));
  const seen = new Map<string, NamedPerson>();
  const add = (raw: string, item: Item) => {
    const name = cleanName(plainName(raw));
    if (!name) return;
    const key = name.toLowerCase();
    if (!seen.has(key)) seen.set(key, { name, company: shortName(item.company), symbol: item.symbol });
  };
  for (const item of sorted) {
    const card = item.card;
    if (card && card.type === "management" && card.status !== "failed") for (const person of card.people) if (person.name) add(person.name, item);
    for (const field of [item.headline, item.subject, item.body]) {
      for (const match of field.matchAll(HONORIFIC)) add(match[1], item);
    }
  }
  return [...seen.values()];
}

// ----------------------------------------------------------------------------------------------------------------------- the search box
export type Suggestion = { kind: "company" | "person" | "topic" | "typed"; id: string; label: string; detail: string };

export type Universe = { companies: readonly { symbol: string; name: string; sector?: string }[]; people: readonly NamedPerson[] };

export function isFollowed(follow: Follow, kind: Suggestion["kind"], id: string): boolean {
  if (kind === "company") return follow.companies.includes(id);
  if (kind === "topic") return follow.topics.includes(id);
  return follow.people.some((p) => p.toLowerCase() === id.toLowerCase());
}

/**
 * What the search box offers for what was typed: companies by name or symbol (a name that starts with it first), people by name,
 * topics by label, and, if it looks like a person's full name that is not already listed, "follow this name". Nothing for an empty box.
 */
export function suggest(query: string, universe: Universe, limit = 8): Suggestion[] {
  const q = query.trim().replace(/\s+/g, " ");
  if (q.length === 0) return [];
  const lower = q.toLowerCase();
  const rank = (text: string) => (text.toLowerCase().startsWith(lower) ? 0 : text.toLowerCase().split(/[\s&-]+/).some((w) => w.startsWith(lower)) ? 1 : 2);
  const out: { s: Suggestion; r: number }[] = [];
  for (const c of universe.companies) {
    const label = shortName(c.name);
    if (c.symbol.toLowerCase().startsWith(lower) || c.name.toLowerCase().includes(lower) || label.toLowerCase().includes(lower)) {
      out.push({ s: { kind: "company", id: c.symbol, label, detail: `Company · ${c.symbol}` }, r: c.symbol.toLowerCase().startsWith(lower) ? 0 : rank(label) });
    }
  }
  for (const p of universe.people) {
    if (p.name.toLowerCase().includes(lower)) out.push({ s: { kind: "person", id: p.name, label: p.name, detail: `Person · named in a ${p.company} filing` }, r: rank(p.name) });
  }
  for (const t of TOPICS) {
    if (t.label.toLowerCase().includes(lower) || t.id.replace(/_/g, " ").includes(lower)) out.push({ s: { kind: "topic", id: t.id, label: t.label, detail: "Topic · filings of this kind" }, r: rank(t.label) });
  }
  out.sort((a, b) => a.r - b.r);
  const result = out.map((x) => x.s).slice(0, limit);
  const known = universe.people.some((p) => p.name.toLowerCase() === lower);
  if (!known && isFullName(q) && /^[\p{L}][\p{L} .'’-]*$/u.test(q)) result.push({ kind: "typed", id: q, label: q, detail: "Person · matched by this exact name in filings" });
  return result;
}

// ------------------------------------------------------------------------------------------------------------------------- empty states
/** "No filings about Kaynes Technology in the last 7 days." The window is written the way the Brief writes it. */
export function nothingLine(label: string, windowText: string): string {
  return `No filings about ${label} in the last ${windowText}.`;
}
