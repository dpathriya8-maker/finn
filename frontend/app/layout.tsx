import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
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
        {/* Phone-sized column, centred on wider screens. */}
        <div className="mx-auto flex min-h-dvh w-full max-w-[430px] flex-col bg-surface md:border-x md:border-line">
          {children}
        </div>
      </body>
    </html>
  );
}
