"use client";

import { useEffect, useState } from "react";

export type LoadState<T> = { kind: "loading" } | { kind: "ready"; data: T } | { kind: "error" };

/** Loads a static JSON file at run time (not baked into the build), so a data refresh needs no rebuild. */
export function useJson<T>(url: string): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch(url, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`${url} returned ${res.status}`);
        return res.json() as Promise<T>;
      })
      .then((data) => {
        if (!cancelled) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return state;
}
