import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { BottomNav } from "@/components/BottomNav";
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
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#14161b" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {/* Phone-sized column, centred on wider screens. The header and the nav stay mounted as you move
            between tabs, so the engine status is not re-checked on every tap. */}
        <div className="mx-auto flex min-h-dvh w-full max-w-[430px] flex-col bg-surface md:border-x md:border-line">
          <header className="px-5 pb-3 pt-[max(1.25rem,env(safe-area-inset-top))]">
            {/* Fixed row height: the pill grows from 32px to 44px when it becomes a Retry button. */}
            <div className="flex min-h-11 items-center justify-between gap-3">
              <p className="text-xl font-bold tracking-[0.18em]">FINN</p>
              <StatusPill />
            </div>
          </header>
          <main className="flex-1 px-5 pb-28">{children}</main>
          <BottomNav />
        </div>
      </body>
    </html>
  );
}
