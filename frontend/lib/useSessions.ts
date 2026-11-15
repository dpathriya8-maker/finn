"use client";

import { useJson } from "@/lib/useJson";
import type { Session } from "@/lib/types";

type CompanyFile = { generated_at: string; signals?: Session[] };

/**
 * The stored price sessions of any company the pipeline has processed (a portfolio company or a research one), read from
 * its own data file. A company with no file, or no sessions, gives nothing, and the screen shows no price rather than a made-up one.
 */
export function useCompanyPrices(symbol: string): { sessions?: Session[]; generatedAt?: string } {
  const state = useJson<CompanyFile>(`/data/${encodeURIComponent(symbol)}.json`);
  if (state.kind !== "ready" || !Array.isArray(state.data.signals) || state.data.signals.length === 0) return {};
  return { sessions: state.data.signals, generatedAt: state.data.generated_at };
}
