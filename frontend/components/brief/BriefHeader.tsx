"use client";

import { WindowHeader } from "@/components/WindowHeader";
import { useGreeting } from "@/lib/profile";

/** "Good evening · Sun, 15 Nov", or "Good evening, Asha · Sun, 15 Nov" if the reader gave a name under You. Local time, local date. */
function Greeting() {
  const text = useGreeting();
  // Empty until the page is on the device (the server cannot know its clock); the line keeps its height so nothing jumps.
  return <p className="min-h-4 truncate text-xs font-medium text-ink-faint">{text}</p>;
}

/** The Brief's heading: a greeting, "Today's Highlights", the time-window button, and when the data was last updated. */
export function BriefHeader() {
  return (
    <WindowHeader above={<Greeting />} widen />
  );
}
