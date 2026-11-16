import { describe, expect, it } from "vitest";
import { isStale, STALE_AFTER_MS } from "@/lib/freshness";

const MADE = "2026-11-15T21:12:19+05:30";
const made = Date.parse(MADE);

describe("stale data", () => {
  it("is not stale within a day of when it was made", () => {
    expect(isStale(MADE, made)).toBe(false);
    expect(isStale(MADE, made + STALE_AFTER_MS)).toBe(false); // exactly 24 hours is not more than 24 hours
  });

  it("is stale once it is more than 24 hours old", () => {
    expect(isStale(MADE, made + STALE_AFTER_MS + 1)).toBe(true);
    expect(isStale(MADE, made + 10 * 24 * 3_600_000)).toBe(true);
  });

  it("is never called stale because of a missing or unreadable date", () => {
    expect(isStale(null, made)).toBe(false);
    expect(isStale(undefined, made)).toBe(false);
    expect(isStale("not a date", made)).toBe(false);
  });

  it("is not stale when the device clock is behind the data", () => {
    expect(isStale(MADE, made - 3 * 24 * 3_600_000)).toBe(false);
  });
});
