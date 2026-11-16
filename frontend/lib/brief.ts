import type { Brief, Item } from "@/lib/types";

/** Priority groups. Weights live in config/categories.json; a filing at or above HIGH_MIN needs attention. */
export const HIGH_MIN = 75;
export const MEDIUM_MIN = 45;
/** Never more than five at a time (design rule: chunk into groups of five or fewer). */
export const GROUP_LIMIT = 5;

export type Groups = { high: Item[]; medium: Item[]; low: Item[]; routine: Item[] };

const HOUR_MS = 3_600_000;
const IST = "Asia/Kolkata";

/**
 * Items inside the window that ends at the data's own timestamp (not the viewer's clock), so a weekend
 * or a stale file still shows its latest day instead of an empty screen. Muted companies are dropped.
 */
export function selectItems(brief: Brief, hours: number, muted: readonly string[] = []): Item[] {
  const end = Date.parse(brief.generated_at);
  const start = end - hours * HOUR_MS;
  const hidden = new Set(muted);
  return brief.items.filter((item) => {
    const at = Date.parse(item.published_at);
    return at >= start && at <= end + 60_000 && !hidden.has(item.symbol);
  });
}

/** Most important first; newest first among equals. Routine filings are kept apart from the rest. */
export function groupItems(items: readonly Item[]): Groups {
  const sorted = [...items].sort(
    (a, b) => b.priority - a.priority || Date.parse(b.published_at) - Date.parse(a.published_at),
  );
  const groups: Groups = { high: [], medium: [], low: [], routine: [] };
  for (const item of sorted) {
    if (item.routine) groups.routine.push(item);
    else if (item.priority >= HIGH_MIN) groups.high.push(item);
    else if (item.priority >= MEDIUM_MIN) groups.medium.push(item);
    else groups.low.push(item);
  }
  return groups;
}

/** One company's filings in the window, most important first. `top` is the priority of the first. */
export type CompanyGroup = { symbol: string; company: string; items: Item[]; top: number };

/**
 * The filings that matter (high and medium), gathered under one company each. Companies come in the order of
 * their most important filing, so a risk anywhere in a company brings the whole company up. Within a company the
 * order is the same: most important first, newest first among equals. Input must already be sorted that way
 * (`groupItems` does it), which makes the first filing seen for a company its top one.
 */
export function groupByCompany(items: readonly Item[]): CompanyGroup[] {
  const byCompany = new Map<string, CompanyGroup>();
  for (const item of items) {
    const group = byCompany.get(item.symbol);
    if (group) group.items.push(item);
    else byCompany.set(item.symbol, { symbol: item.symbol, company: item.company, items: [item], top: item.priority });
  }
  return [...byCompany.values()];
}

/** The two priority sections of the Brief as companies: those with a filing at HIGH_MIN or above, and the rest. */
export function companySections(groups: Groups): { needs: CompanyGroup[]; worth: CompanyGroup[] } {
  const all = groupByCompany([...groups.high, ...groups.medium]);
  return { needs: all.filter((g) => g.top >= HIGH_MIN), worth: all.filter((g) => g.top < HIGH_MIN) };
}

export type SummaryPart = { text: string; tone?: "bad" | "good" };

/**
 * The one line under the Brief's heading, worked out in code from the filings in the window (never by a model). What applies is
 * joined with " · ": "2 risks to review", and "Busy day: 6 of your companies filed" when five or more companies have a material
 * filing. With nothing material it says so: "Quiet day: nothing needs action across your 18 companies". A risk is a material filing
 * the Brief tags Risk. If something material is there but it is neither a risk nor a busy day, it says how many are worth a look.
 */
export function summaryParts(groups: Groups, companyCount: number): SummaryPart[] {
  const material = [...groups.high, ...groups.medium];
  if (material.length === 0) {
    return [{ text: `Quiet day: nothing needs action across your ${companyCount} ${companyCount === 1 ? "company" : "companies"}`, tone: "good" }];
  }
  const risks = material.filter((item) => item.tone === "bad").length;
  const filed = new Set(material.map((item) => item.symbol)).size;
  const parts: SummaryPart[] = [];
  if (risks > 0) parts.push({ text: `${risks} ${risks === 1 ? "risk" : "risks"} to review`, tone: "bad" });
  if (filed >= BUSY_COMPANIES) parts.push({ text: `Busy day: ${filed} of your companies filed` });
  if (parts.length === 0) parts.push({ text: `${material.length} ${material.length === 1 ? "filing" : "filings"} worth a look` });
  return parts;
}

export function summaryLine(groups: Groups, companyCount: number): string {
  return summaryParts(groups, companyCount).map((part) => part.text).join(" · ");
}

/** A day is busy when this many of the reader's companies have something material. */
export const BUSY_COMPANIES = 5;

/** The count of material filings: what needs attention plus what is worth a look. */
export function thingsThatMatter(groups: Groups): number {
  return groups.high.length + groups.medium.length;
}

/** The India calendar day of a moment, "2026-11-15". */
export function istDate(ms: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: IST, year: "numeric", month: "2-digit", day: "2-digit" }).format(ms);
}

/** "Today, 6:23 pm", "Yesterday, 6:23 pm" or "13 Nov, 6:23 pm", counted from the data's own timestamp. */
export function whenLabel(iso: string, referenceIso: string): string {
  const at = Date.parse(iso);
  const ref = Date.parse(referenceIso);
  if (Number.isNaN(at) || Number.isNaN(ref)) return "";
  const time = new Intl.DateTimeFormat("en-IN", { timeZone: IST, hour: "numeric", minute: "2-digit", hour12: true }).format(at);
  const day = istDate(at);
  if (day === istDate(ref)) return `Today, ${time}`;
  if (day === istDate(ref - 24 * HOUR_MS)) return `Yesterday, ${time}`;
  const date = new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "short" }).format(at);
  return `${date}, ${time}`;
}

export const WINDOWS = [
  { hours: 24, label: "24 hours" },
  { hours: 72, label: "3 days" },
  { hours: 168, label: "7 days" },
] as const;

/**
 * The window the Brief actually shows. A reader who picked a window gets exactly that one. A reader who did not gets the default
 * (24 hours) unless it holds nothing material, in which case the Brief looks back to the next window that does (3 days, then 7) and
 * says so; if none holds anything material it stays on the default. Always counted from the data's own time, never the device clock.
 */
export function effectiveWindow(brief: Brief, hours: number, chosen: boolean, muted: readonly string[] = []): { hours: number; widened: boolean } {
  if (chosen) return { hours, widened: false };
  for (const w of WINDOWS) {
    if (w.hours < hours) continue;
    const groups = groupItems(selectItems(brief, w.hours, muted));
    if (thingsThatMatter(groups) > 0) return { hours: w.hours, widened: w.hours !== hours };
  }
  return { hours, widened: false };
}

/** The Brief's heading: "Today's Highlights" for the last day, otherwise "Highlights: last 3 days". */
export function highlightsTitle(hours: number): string {
  return hours === 24 ? "Today's Highlights" : `Highlights: last ${windowLabel(hours)}`;
}

export function windowLabel(hours: number): string {
  return WINDOWS.find((w) => w.hours === hours)?.label ?? `${hours} hours`;
}

/** Plain-English "what changed" for a stale part: "announcements (as of 14 Nov, 6:00 pm)". */
export function staleNotes(brief: Brief): string[] {
  return brief.companies
    .filter((c) => Object.keys(c.stale).length > 0)
    .map((c) => {
      const parts = Object.entries(c.stale).map(([part, since]) => `${part} as of ${whenLabel(since, brief.generated_at)}`);
      return `${c.symbol}: ${parts.join(", ")}`;
    });
}
