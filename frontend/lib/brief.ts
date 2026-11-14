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

/** The "N things that matter" in the headline: what needs attention plus what is worth a look. */
export function thingsThatMatter(groups: Groups): number {
  return groups.high.length + groups.medium.length;
}

function istDate(ms: number): string {
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
