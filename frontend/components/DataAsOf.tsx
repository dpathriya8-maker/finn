"use client";

import { useEffect, useState } from "react";
import { formatIst } from "@/lib/format";

type Meta = { generated_at: string; note?: string };
type State = { kind: "loading" } | { kind: "ready"; meta: Meta } | { kind: "error" };

/**
 * "Data as of ..." from the static file the pipeline writes to public/data/meta.json.
 * Fetched at run time (not baked into the build), which is the same path the Morning Brief
 * will use. Sample data is labelled as such; a missing file is said out loud, never hidden.
 */
export function DataAsOf({ stale = false }: { stale?: boolean }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch("/data/meta.json", { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`meta.json returned ${res.status}`);
        return res.json() as Promise<Meta>;
      })
      .then((meta) => {
        if (!cancelled) setState({ kind: "ready", meta });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return <p className="h-5 w-48 animate-pulse rounded bg-line" aria-label="Loading data time" />;
  }
  if (state.kind === "error") {
    return <p className="font-medium text-watch">Data unavailable right now</p>;
  }
  const isSample = state.meta.note === "skeleton";
  return (
    <p className={stale ? "font-medium text-watch" : undefined}>
      Data as of {formatIst(state.meta.generated_at)}
      {isSample && <span className="ml-2 rounded bg-watch-bg px-1.5 py-0.5 text-xs font-medium text-watch">Sample data</span>}
    </p>
  );
}
