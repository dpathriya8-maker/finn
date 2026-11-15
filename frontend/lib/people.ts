import { shortName } from "@/lib/headline";
import type { Brief } from "@/lib/types";

/** A person named in a real management-change filing. Every field is a literal piece of that filing, found by rules. */
export type PersonEntry = {
  /** Stable id for following: the symbol and the name as filed. */
  id: string;
  name: string;
  role: string;
  /** "appointed", "resigned" and so on, from the filing's own kind. */
  action: string;
  company: string;
  symbol: string;
  /** Date of the filing, ISO. */
  filed: string;
  url: string | null;
};

const ACTION: Record<string, string> = {
  appointment: "appointed",
  "re-appointment": "re-appointed",
  redesignation: "redesignated",
  resignation: "resigned",
  retirement: "retiring",
  cessation: "ceased",
  death: "passed away",
  removal: "removed",
};

export function actionWords(kind: string): string {
  return ACTION[kind] ?? kind.replace(/_/g, " ");
}

/** The name without its honorific, for initials: "Mr. V. Srinivasa Rangan" -> "V. Srinivasa Rangan". */
export function plainName(name: string): string {
  return name.replace(/^(?:mr|mrs|ms|miss|dr|shri|smt|prof|capt|col)\.?\s+/i, "").trim() || name;
}

/** People from the management-change cards in the brief, newest filing first, one entry per person and company. */
export function peopleFromBrief(brief: Pick<Brief, "items">): PersonEntry[] {
  const seen = new Map<string, PersonEntry>();
  const items = [...brief.items].sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at));
  for (const item of items) {
    const card = item.card;
    if (!card || card.type !== "management" || card.status === "failed") continue;
    for (const person of card.people) {
      const id = `${item.symbol}:${person.name}`;
      if (seen.has(id) || !person.name) continue;
      seen.set(id, {
        id,
        name: person.name,
        role: person.role,
        action: actionWords(person.kind),
        company: shortName(item.company),
        symbol: item.symbol,
        filed: item.published_at,
        url: item.url,
      });
    }
  }
  return [...seen.values()];
}
