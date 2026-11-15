"use client";

import { createContext, useContext, type ReactNode } from "react";

const Ctx = createContext<ReadonlyMap<string, string>>(new Map());

/**
 * Why each filing is in the Following feed, by filing id ("Because you follow Kaynes Technology, Results"). The Brief cards read it
 * to add one grey line; outside the Following feed the map is empty and the cards are exactly the Brief's.
 */
export function BecauseProvider({ value, children }: { value: ReadonlyMap<string, string>; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useBecause(itemId: string): string | undefined {
  return useContext(Ctx).get(itemId);
}
