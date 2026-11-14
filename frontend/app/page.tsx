import { BottomNav } from "@/components/BottomNav";
import { DataAsOf } from "@/components/DataAsOf";
import { FilingsList } from "@/components/FilingsList";
import { StatusPill } from "@/components/StatusPill";

export default function Home() {
  return (
    <>
      <header className="px-5 pb-3 pt-[max(1.25rem,env(safe-area-inset-top))]">
        {/* Fixed row height: the pill grows from 32px to 44px when it becomes a Retry button. */}
        <div className="flex min-h-11 items-center justify-between gap-3">
          <p className="text-xl font-bold tracking-[0.18em]">FINN</p>
          <StatusPill />
        </div>
      </header>

      <main className="flex-1 px-5 pb-28">
        <section aria-labelledby="brief-title" className="pt-4">
          <h1 id="brief-title" className="text-2xl font-semibold tracking-tight">
            Morning Brief
          </h1>
          <div className="mt-1 text-sm text-ink-soft">
            <DataAsOf />
          </div>
        </section>

        <div className="mt-6">
          <FilingsList />
        </div>
      </main>

      <BottomNav />
    </>
  );
}
