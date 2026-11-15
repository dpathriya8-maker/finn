import { useSyncExternalStore } from "react";

/**
 * Which data refresh the reader last looked at on the Alerts screen, kept in this browser only. The bottom-nav dot uses it to say
 * "there is something new": alerts exist and the data has been refreshed since Alerts was last opened. No count, no sound.
 */
const KEY = "finn.alertsSeen.v1";
const listeners = new Set<() => void>();

function read(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "";
  } catch {
    return ""; // storage blocked: the dot simply stays while there are alerts
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

export function markAlertsSeen(generatedAt: string): void {
  try {
    window.localStorage.setItem(KEY, generatedAt);
  } catch {
    // not saved
  }
  listeners.forEach((listener) => listener());
}

/** True when the reader has not opened Alerts since the data was last refreshed. False on the server, so the first paint has no dot. */
export function useAlertsUnseen(generatedAt: string | undefined): boolean {
  return useSyncExternalStore(
    subscribe,
    () => (generatedAt ? read() !== generatedAt : false),
    () => false,
  );
}
