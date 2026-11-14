import { describe, expect, it } from "vitest";
import { effectiveLabel, kindLabel, lacksProfile, movement, termLabel } from "@/lib/management";
import type { ManagementPerson } from "@/lib/types";

function person(over: Partial<ManagementPerson> = {}): ManagementPerson {
  return {
    name: "Ms. Priya Nair",
    din: null,
    role: "Chief Financial Officer",
    kind: "appointment",
    direction: "in",
    effective: { date: "2026-12-01", text: "1st December 2026" },
    term: null,
    profile: null,
    page: 1,
    ...over,
  };
}

describe("kindLabel", () => {
  it("names each kind of change the pipeline reports, and falls back to a plain label", () => {
    expect(kindLabel("re-appointment")).toBe("Re-appointment");
    expect(kindLabel("redesignation")).toBe("New designation");
    expect(kindLabel("death")).toBe("Demise");
    expect(kindLabel("something new")).toBe("Management change");
  });
});

describe("movement", () => {
  it("says whether someone is joining, leaving or staying, in words", () => {
    expect(movement(person())).toBe("Joining");
    expect(movement(person({ kind: "resignation", direction: "out" }))).toBe("Leaving");
    expect(movement(person({ kind: "retirement", direction: "out" }))).toBe("Leaving");
    expect(movement(person({ kind: "re-appointment", direction: "in" }))).toBe("Continuing");
    expect(movement(person({ kind: "redesignation", direction: "in" }))).toBe("New role");
    expect(movement(person({ kind: "change", direction: "" }))).toBe("");
  });
});

describe("effectiveLabel and termLabel", () => {
  it("formats the filing's date and keeps its own words if the date cannot be read", () => {
    expect(effectiveLabel(person())).toBe("1 Dec 2026");
    expect(effectiveLabel(person({ effective: { date: "not a date", text: "the first of December" } }))).toBe("the first of December");
    expect(effectiveLabel(person({ effective: null }))).toBeNull();
  });
  it("words a term", () => {
    expect(termLabel(person({ term: "1 year" }))).toBe("for 1 year");
    expect(termLabel(person())).toBeNull();
  });
});

describe("lacksProfile", () => {
  it("is true only for someone new who joins and whose filing has no profile", () => {
    expect(lacksProfile(person())).toBe(true);
    expect(lacksProfile(person({ profile: { text: "A chartered accountant.", page: 4, source: "filing" } }))).toBe(false);
    expect(lacksProfile(person({ kind: "re-appointment" }))).toBe(false); // already known to the company
    expect(lacksProfile(person({ kind: "resignation", direction: "out" }))).toBe(false); // nobody to introduce
  });
});
