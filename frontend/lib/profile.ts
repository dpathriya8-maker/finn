import { useSyncExternalStore } from "react";

/**
 * "You" without an account: an optional name the reader chooses to give, kept in this browser's localStorage and
 * nowhere else. It is used for the greeting and the initials circle, and for nothing else. No name is ever sent anywhere.
 */
const KEY = "finn.profile.v1";
const MAX_NAME = 40;
const listeners = new Set<() => void>();

/** Trimmed, one space between words, no control characters or angle brackets, at most 40 characters. */
export function cleanName(raw: string): string {
  const text = raw.replace(/[\p{Cc}<>]/gu, "").replace(/\s+/g, " ").trim();
  return Array.from(text).slice(0, MAX_NAME).join("").trim();
}

/** Up to two capital letters: the first letters of the first two words ("Asha Rao" -> "AR", "Asha" -> "A"). Empty for no name. */
export function nameInitials(name: string): string {
  const words = cleanName(name).split(" ").filter((w) => /\p{L}/u.test(w));
  return words
    .slice(0, 2)
    .map((w) => (Array.from(w).find((ch) => /\p{L}/u.test(ch)) ?? "").toUpperCase())
    .join("");
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** "Good morning" before noon, "Good afternoon" until 5 pm, "Good evening" after, by the clock of the device. */
export function salutation(hour: number): string {
  return hour >= 5 && hour < 12 ? "Good morning" : hour >= 12 && hour < 17 ? "Good afternoon" : "Good evening";
}

/** "Good evening, Asha · Sun, 15 Nov", or without the name: "Good evening · Sun, 15 Nov". Local time and local date. */
export function greetingFor(now: Date, name: string): string {
  const who = cleanName(name);
  return `${salutation(now.getHours())}${who ? `, ${who}` : ""} · ${DAYS[now.getDay()]}, ${now.getDate()} ${MONTHS[now.getMonth()]}`;
}

function readName(): string {
  try {
    const data: unknown = JSON.parse(window.localStorage.getItem(KEY) ?? "{}");
    const name = typeof data === "object" && data !== null ? (data as Record<string, unknown>).name : "";
    return typeof name === "string" ? cleanName(name) : "";
  } catch {
    return ""; // private mode, blocked storage or a damaged value: no name, and nothing breaks
  }
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", callback);
  };
}

/** Save the name ("" clears it) and tell every screen that shows it. */
export function setProfileName(raw: string): void {
  const name = cleanName(raw);
  try {
    if (name) window.localStorage.setItem(KEY, JSON.stringify({ name }));
    else window.localStorage.removeItem(KEY);
  } catch {
    // storage unavailable: the name is not kept, and the screen simply keeps the old one
  }
  listeners.forEach((listener) => listener());
}

/** The saved name, "" if none. Always "" on the server and on first paint, so the page hydrates cleanly. */
export function useProfileName(): string {
  return useSyncExternalStore(subscribe, readName, () => "");
}

/**
 * The Brief's greeting. Empty on the server and on first paint (the time is the device's, which the server cannot know), then it
 * fills in; it also moves on by itself when the hour changes while the page stays open.
 */
export function useGreeting(): string {
  const name = useProfileName();
  return useSyncExternalStore(
    (callback) => {
      const stop = subscribe(callback);
      const timer = window.setInterval(callback, 60_000);
      return () => {
        stop();
        window.clearInterval(timer);
      };
    },
    () => greetingFor(new Date(), name),
    () => "",
  );
}
