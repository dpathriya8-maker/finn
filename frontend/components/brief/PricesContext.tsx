"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { Brief, Session } from "@/lib/types";

type Prices = { sessions: Map<string, Session[]>; generatedAt: string | undefined };

const Ctx = createContext<Prices>({ sessions: new Map(), generatedAt: undefined });

/** The price sessions in brief.json, by symbol, so every card in the Brief can show its company's price without its own request. */
export function PricesProvider({ brief, children }: { brief: Brief; children: ReactNode }) {
  const value = useMemo(
    () => ({ sessions: new Map(brief.signals.map((s) => [s.symbol, s.sessions])), generatedAt: brief.generated_at }),
    [brief],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useBriefPrices(symbol: string): { sessions: Session[] | undefined; generatedAt: string | undefined } {
  const { sessions, generatedAt } = useContext(Ctx);
  return { sessions: sessions.get(symbol), generatedAt };
}

/** Every company's stored sessions in the brief, for a screen that adds them up (the portfolio summary). */
export function useAllBriefPrices(): { sessions: Map<string, Session[]>; generatedAt: string | undefined } {
  return useContext(Ctx);
}
