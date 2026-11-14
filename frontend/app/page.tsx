import { MorningBrief } from "@/components/brief/MorningBrief";
import { DataAsOf } from "@/components/DataAsOf";

export default function Home() {
  return (
    <>
      <section aria-labelledby="brief-title" className="pt-4">
        <h1 id="brief-title" className="text-2xl font-semibold tracking-tight">
          Morning Brief
        </h1>
        <div className="mt-1 text-sm text-ink-soft">
          <DataAsOf />
        </div>
      </section>

      <div className="mt-5">
        <MorningBrief />
      </div>
    </>
  );
}
