"use client";

import { useEffect, useState } from "react";

export type LoadState<T> = { kind: "loading" } | { kind: "ready"; data: T } | { kind: "error" };

// One request per file per page load, shared by every component that asks for it (the nav badge, the
// Brief and the Alerts screen all read the same brief.json). A failed request is forgotten so the next
// screen can try again.
const requests = new Map<string, Promise<unknown>>();

function load<T>(url: string): Promise<T> {
  let request = requests.get(url);
  if (!request) {
    // The browser's own cache rules: the data files are served `must-revalidate`, so each page load asks whether the file changed and
    // gets a fresh one the moment the pipeline has published it. (`no-store` would also have made the preload above unusable.)
    request = fetch(url).then((res) => {
      if (!res.ok) throw new Error(`${url} returned ${res.status}`);
      return res.json();
    });
    request.catch(() => requests.delete(url));
    requests.set(url, request);
  }
  return request as Promise<T>;
}

/** Loads a static JSON file at run time (not baked into the build), so a data refresh needs no rebuild. */
export function useJson<T>(url: string): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    load<T>(url)
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
