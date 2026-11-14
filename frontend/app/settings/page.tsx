import type { Metadata } from "next";
import { SettingsScreen } from "@/components/settings/SettingsScreen";

export const metadata: Metadata = { title: "Settings · FINN" };

export default function SettingsPage() {
  return (
    <>
      <section aria-labelledby="settings-title" className="pt-4">
        <h1 id="settings-title" className="text-2xl font-semibold tracking-tight">
          Settings
        </h1>
        <p className="mt-1 text-sm text-ink-soft">You decide what counts as news.</p>
      </section>

      <div className="mt-5">
        <SettingsScreen />
      </div>
    </>
  );
}
