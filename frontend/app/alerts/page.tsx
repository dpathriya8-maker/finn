import type { Metadata } from "next";
import { AlertsScreen } from "@/components/alerts/AlertsScreen";
import { WindowHeader } from "@/components/WindowHeader";

export const metadata: Metadata = { title: "Alerts · FINN" };

export default function AlertsPage() {
  return (
    <>
      <WindowHeader title="Alerts">
        <p className="mt-1 text-sm text-ink-soft">Only what crosses your own lines.</p>
      </WindowHeader>

      <div className="mt-5">
        <AlertsScreen />
      </div>
    </>
  );
}
