/** How a management-change card is shown. The facts arrive from the pipeline, read out of the filing; this only words them. */
import type { ManagementPerson } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  appointment: "Appointment",
  "re-appointment": "Re-appointment",
  redesignation: "New designation",
  resignation: "Resignation",
  retirement: "Retirement",
  cessation: "Cessation",
  death: "Demise",
  removal: "Removal",
};

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? "Management change";
}

/** Joining, leaving or staying, so the direction reads at a glance and never depends on colour. */
export function movement(person: Pick<ManagementPerson, "kind" | "direction">): string {
  if (person.kind === "re-appointment") return "Continuing";
  if (person.kind === "redesignation") return "New role";
  if (person.direction === "in") return "Joining";
  if (person.direction === "out") return "Leaving";
  return "";
}

const DAY = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" });

/** "23 Nov 2026" from the filing's date, or the filing's own words if the date cannot be parsed. */
export function effectiveLabel(person: Pick<ManagementPerson, "effective">): string | null {
  if (!person.effective) return null;
  const date = new Date(`${person.effective.date}T12:00:00+05:30`);
  return Number.isNaN(date.getTime()) ? person.effective.text : DAY.format(date);
}

/** "1 year", written as "for 1 year". */
export function termLabel(person: Pick<ManagementPerson, "term">): string | null {
  return person.term ? `for ${person.term}` : null;
}

/** True when a reader would expect a bio (someone new is joining) and the filing has none. */
export function lacksProfile(person: ManagementPerson): boolean {
  return person.direction === "in" && person.kind !== "re-appointment" && person.profile === null;
}
