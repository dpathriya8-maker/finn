import type { Metadata, Viewport } from "next";
import { preload } from "react-dom";
import type { ReactNode } from "react";
import { BottomNav } from "@/components/BottomNav";
import { FinnMark } from "@/components/FinnMark";
import { StatusPill } from "@/components/StatusPill";
import "./globals.css";

export const metadata: Metadata = {
  title: "FINN",
  description:
    "A calm morning brief of what changed in your portfolio, and research grounded only in company filings.",
  applicationName: "FINN",
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/apple-touch-icon.png",
  },
  appleWebApp: { capable: true, title: "FINN", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f4ee" },
    { media: "(prefers-color-scheme: dark)", color: "#1c1f2e" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // The two data files every screen reads (the nav's alerts dot, the Brief, Alerts, You) start downloading with the page, not after
  // the scripts have run and asked for them.
  preload("/data/brief.json", { as: "fetch", crossOrigin: "anonymous" });
  preload("/data/config.json", { as: "fetch", crossOrigin: "anonymous" });
  return (
    <html lang="en">
      <body>
        {/* Phone-sized column, centred on wider screens. The header and the nav stay mounted as you move
            between tabs, so the engine status is not re-checked on every tap. It is `relative` and clips sideways overflow:
            nothing inside can widen the page, and the nav below is a child of this same column (sticky, not fixed), so
            it always has exactly the column's width and position. */}
        <div className="relative mx-auto flex min-h-dvh w-full max-w-[430px] flex-col overflow-x-clip bg-page md:border-x md:border-line">
          <header className="px-5 pb-3 pt-[max(1.25rem,env(safe-area-inset-top))]">
            {/* Fixed row height: the pill grows from 32px to 44px when it becomes a Retry button. */}
            <div className="flex min-h-11 items-center justify-between gap-3">
              <p className="flex items-center gap-2.5 text-xl font-bold tracking-[0.18em]">
                <FinnMark />
                FINN
              </p>
              <StatusPill />
            </div>
          </header>
          <main className="min-w-0 flex-1 px-5 pb-8">{children}</main>
          <BottomNav />
        </div>
      </body>
    </html>
  );
}
