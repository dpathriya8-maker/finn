import type { Metadata } from "next";
import { YouScreen } from "@/components/settings/YouScreen";

export const metadata: Metadata = { title: "You · FINN" };

// The route stays /settings so every existing link (the Brief's "Manage" muted companies, saved shortcuts) keeps working.
export default function YouPage() {
  return (
    <>
      <section aria-labelledby="you-title" className="pt-4">
        <h1 id="you-title" className="text-2xl font-semibold tracking-tight">
          You
        </h1>
      </section>

      <div className="mt-4">
        <YouScreen />
      </div>
    </>
  );
}
