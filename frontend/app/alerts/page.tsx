import type { Metadata } from "next";
import { AlertsScreen } from "@/components/alerts/AlertsScreen";

export const metadata: Metadata = { title: "Alerts · FINN" };

export default function AlertsPage() {
  return (
    <>
      <section aria-labelledby="alerts-title" className="pt-4">
        <h1 id="alerts-title" className="text-2xl font-semibold tracking-tight">
          Alerts
        </h1>
        <p className="mt-1 text-sm text-ink-soft">Only what crosses your own lines.</p>
      </section>

      <div className="mt-5">
        <AlertsScreen />
      </div>
    </>
  );
}
