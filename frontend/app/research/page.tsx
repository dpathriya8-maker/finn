import type { Metadata } from "next";
import { Suspense } from "react";
import { ResearchScreen } from "@/components/research/ResearchScreen";

export const metadata: Metadata = { title: "Research · FINN" };

export default function ResearchPage() {
  return (
    <>
      <section aria-labelledby="research-title" className="pt-4">
        <h1 id="research-title" className="text-2xl font-semibold tracking-tight">
          Research
        </h1>
        <p className="mt-1 text-sm text-ink-soft">What management promised, and whether it happened. Only from the company’s own filings.</p>
      </section>

      <div className="mt-5">
        <Suspense fallback={<div className="h-40 animate-pulse rounded-2xl bg-line" aria-label="Loading" />}>
          <ResearchScreen />
        </Suspense>
      </div>
    </>
  );
}
