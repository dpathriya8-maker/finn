"use client";

import { useEffect, useRef, useState } from "react";
import { BriefHeader } from "@/components/brief/BriefHeader";
import { InterestedTab } from "@/components/brief/InterestedTab";
import { MorningBrief } from "@/components/brief/MorningBrief";

const TABS = [
  { id: "invested", label: "Invested" },
  { id: "interested", label: "Interested" },
] as const;

/**
 * The Brief screen: its heading, then two tabs you can tap or swipe between. Invested is the Morning Brief as it
 * always was; Interested is the concept preview of a watchlist. Swiping is native scroll-snap, so it is smooth, and it
 * is instant for readers who ask for reduced motion. The tab that is not showing is collapsed once the swipe settles,
 * so the page is only as tall as what you are looking at.
 */
export function BriefHome() {
  const [active, setActive] = useState(0);
  const [moving, setMoving] = useState(false);
  const [warm, setWarm] = useState(false); // the Brief has settled: get the other tab ready so a swipe is instant
  const scroller = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const target = useRef<number | null>(null); // the tab a tap asked for, until the scroll has arrived

  useEffect(() => () => window.clearTimeout(timer.current), []);

  // The Interested tab loads six data files and draws a long list. It is not on screen at first, so it waits until the reader
  // goes there (or the Brief has had a few seconds to itself), which keeps the first screen fast.
  useEffect(() => {
    const id = window.setTimeout(() => setWarm(true), 3000);
    return () => window.clearTimeout(id);
  }, []);

  /** The scroll has stopped: finish the trip if a tap's animation stalled, then settle on the panel we are at. */
  function settle() {
    const el = scroller.current;
    if (!el || el.clientWidth === 0) return;
    const asked = target.current;
    target.current = null;
    if (asked !== null && Math.round(el.scrollLeft / el.clientWidth) !== asked) el.scrollTo({ left: asked * el.clientWidth, behavior: "auto" });
    setActive(asked ?? Math.round(el.scrollLeft / el.clientWidth));
    setMoving(false);
  }

  function go(index: number) {
    const el = scroller.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.current = index;
    setActive(index);
    setMoving(true);
    el.scrollTo({ left: index * el.clientWidth, behavior: reduce ? "auto" : "smooth" });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(settle, reduce ? 60 : 500);
  }

  function onScroll() {
    const el = scroller.current;
    if (!el || el.clientWidth === 0) return;
    setMoving(true);
    if (target.current === null) setActive(Math.round(el.scrollLeft / el.clientWidth)); // a swipe: follow the finger
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(settle, 160);
  }

  return (
    <>
      <BriefHeader />

      <div role="tablist" aria-label="Brief" className="mt-4 grid grid-cols-2 border-b border-line">
        {TABS.map((tab, i) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={active === i}
            aria-controls={`panel-${tab.id}`}
            onClick={() => go(i)}
            className={`-mb-px min-h-11 border-b-2 text-sm font-semibold ${active === i ? "border-accent text-accent" : "border-transparent text-ink-faint"}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div ref={scroller} onScroll={onScroll} className="relative mt-5 flex snap-x snap-mandatory items-start overflow-x-auto overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {TABS.map((tab, i) => {
          const hidden = active !== i && !moving;
          return (
            <section
              key={tab.id}
              role="tabpanel"
              id={`panel-${tab.id}`}
              aria-labelledby={`tab-${tab.id}`}
              inert={hidden}
              className={`w-full shrink-0 snap-start ${hidden ? "h-0 overflow-hidden" : ""}`}
            >
              {tab.id === "invested" ? <MorningBrief /> : warm || active === i || moving ? <InterestedTab /> : null}
            </section>
          );
        })}
      </div>
    </>
  );
}
