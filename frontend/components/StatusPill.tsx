"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

type Status = "checking" | "online" | "waking" | "offline" | "unconfigured";

const ATTEMPT_TIMEOUT_MS = 8_000;
const RETRY_EVERY_MS = 5_000;
const GIVE_UP_AFTER_MS = 150_000;
const SHOW_WAKING_AFTER_MS = 3_000;

// Full class names, so Tailwind can see them. Colour = meaning: green good, amber watch, red bad.
const LOOK: Record<Status, { label: string; tone: string; pulse: boolean }> = {
  checking: { label: "Checking engine…", tone: "bg-line text-ink-soft", pulse: true },
  online: { label: "Engine online", tone: "bg-good-bg text-good", pulse: false },
  waking: { label: "Waking up… (free server, up to 2 min)", tone: "bg-watch-bg text-watch", pulse: true },
  offline: { label: "Engine offline", tone: "bg-bad-bg text-bad", pulse: false },
  unconfigured: { label: "Engine not configured", tone: "bg-bad-bg text-bad", pulse: false },
};

async function isHealthy(signal: AbortSignal): Promise<boolean> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store", signal });
  if (!res.ok) return false;
  const body: unknown = await res.json();
  return (
    typeof body === "object" && body !== null && (body as { status?: unknown }).status === "ok"
  );
}

/**
 * Shows whether the research engine (the FastAPI backend) is reachable.
 * Render's free tier sleeps after 15 idle minutes and takes about a minute to wake, so a slow
 * or failing first answer is shown as "waking up" and retried every 5 s for up to 150 s
 * before the pill gives up and says "offline".
 */
export function StatusPill() {
  const [status, setStatus] = useState<Status>(API_URL ? "checking" : "unconfigured");
  const [run, setRun] = useState(0);

  useEffect(() => {
    if (!API_URL) return;
    const life = new AbortController();
    const startedAt = Date.now();
    const wakingTimer = setTimeout(
      () => setStatus((current) => (current === "checking" ? "waking" : current)),
      SHOW_WAKING_AFTER_MS,
    );

    (async () => {
      while (!life.signal.aborted) {
        const attempt = new AbortController();
        const timeout = setTimeout(() => attempt.abort(), ATTEMPT_TIMEOUT_MS);
        let healthy = false;
        try {
          healthy = await isHealthy(attempt.signal);
        } catch {
          healthy = false;
        } finally {
          clearTimeout(timeout);
        }
        if (life.signal.aborted) return;
        if (healthy) {
          setStatus("online");
          return;
        }
        if (Date.now() - startedAt >= GIVE_UP_AFTER_MS) {
          setStatus("offline");
          return;
        }
        setStatus("waking");
        await new Promise((resolve) => setTimeout(resolve, RETRY_EVERY_MS));
      }
    })();

    return () => {
      life.abort();
      clearTimeout(wakingTimer);
    };
  }, [run]);

  const look = LOOK[status];
  const content = (
    <>
      <span
        aria-hidden="true"
        className={`size-2 rounded-full bg-current ${look.pulse ? "motion-safe:animate-pulse" : ""}`}
      />
      <span>{look.label}</span>
    </>
  );
  const shape = `inline-flex items-center gap-2 rounded-full px-3 text-sm font-medium ${look.tone}`;

  if (status === "offline") {
    return (
      <button
        type="button"
        onClick={() => {
          setStatus("checking");
          setRun((n) => n + 1);
        }}
        className={`${shape} min-h-11`}
      >
        {content}
        <span className="underline underline-offset-2">Retry</span>
      </button>
    );
  }

  return (
    <p role="status" className={`${shape} min-h-8`}>
      {content}
    </p>
  );
}
