"use client";

import type { ResearchIndex } from "@/lib/research";
import { useJson } from "@/lib/useJson";
import type { Brief, Session } from "@/lib/types";

type CompanyFile = { generated_at: string; signals?: Session[] };

/**
 * The stored price sessions of any company the pipeline has processed (a portfolio company or a research one), read from
 * its own data file. A company with no file (a ticker researched live, say), or no sessions, gives nothing, and the screen shows no
 * price rather than a made-up one. The file is only requested for a company the app knows has one, so an unprepared ticker never
 * causes a 404.
 */
export function useCompanyPrices(symbol: string): { sessions?: Session[]; generatedAt?: string } {
  const portfolio = useJson<Brief>("/data/brief.json");
  const research = useJson<ResearchIndex>("/data/research/index.json");
  const known =
    (portfolio.kind === "ready" && portfolio.data.companies.some((c) => c.symbol === symbol)) ||
    (research.kind === "ready" && research.data.companies.some((c) => c.symbol === symbol));
  const state = useJson<CompanyFile>(known ? `/data/${encodeURIComponent(symbol)}.json` : null);
  if (state.kind !== "ready" || !Array.isArray(state.data.signals) || state.data.signals.length === 0) return {};
  return { sessions: state.data.signals, generatedAt: state.data.generated_at };
}
