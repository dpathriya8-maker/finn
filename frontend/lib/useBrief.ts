"use client";

import { useEffect, useState } from "react";
import type { Brief } from "@/lib/types";

export type BriefState =
  | { kind: "loading" }
  | { kind: "ready"; brief: Brief }
  | { kind: "error" };

/** Loads the precomputed feed at run time (not baked into the build), so a data refresh needs no rebuild. */
export function useBrief(): BriefState {
  const [state, setState] = useState<BriefState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch("/data/brief.json", { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`brief.json returned ${res.status}`);
        return res.json() as Promise<Brief>;
      })
      .then((brief) => {
        if (!cancelled) setState({ kind: "ready", brief });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
