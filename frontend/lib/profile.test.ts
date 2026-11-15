import { describe, expect, it } from "vitest";
import { cleanName, greetingFor, nameInitials, salutation } from "@/lib/profile";

describe("the name", () => {
  it("is tidied: trimmed, single spaces, no markup characters, at most 40 characters", () => {
    expect(cleanName("  Asha   Rao ")).toBe("Asha Rao");
    expect(cleanName("<b>Asha</b>")).toBe("bAsha/b");
    expect(cleanName("A\u0000sha\n")).toBe("Asha");
    expect(Array.from(cleanName("x".repeat(80))).length).toBe(40);
    expect(cleanName("   ")).toBe("");
  });

  it("gives up to two capital initials, and none for no name", () => {
    expect(nameInitials("Asha Rao")).toBe("AR");
    expect(nameInitials("asha")).toBe("A");
    expect(nameInitials("Asha Kumari Rao")).toBe("AK");
    expect(nameInitials("  ")).toBe("");
    expect(nameInitials("123 !!")).toBe("");
    expect(nameInitials("आशा राव")).toBe("आर");
  });
});

describe("the greeting", () => {
  it("follows the clock of the device", () => {
    expect(salutation(4)).toBe("Good evening");
    expect(salutation(5)).toBe("Good morning");
    expect(salutation(11)).toBe("Good morning");
    expect(salutation(12)).toBe("Good afternoon");
    expect(salutation(16)).toBe("Good afternoon");
    expect(salutation(17)).toBe("Good evening");
    expect(salutation(23)).toBe("Good evening");
  });

  it("adds the date and, only if there is one, the name", () => {
    const sunday = new Date(2026, 10, 15, 21, 5); // local time: Sunday 15 November 2026, 9:05 pm
    expect(greetingFor(sunday, "")).toBe("Good evening · Sun, 15 Nov");
    expect(greetingFor(sunday, "Asha")).toBe("Good evening, Asha · Sun, 15 Nov");
    expect(greetingFor(new Date(2026, 10, 15, 8, 0), "  ")).toBe("Good morning · Sun, 15 Nov");
  });
});
