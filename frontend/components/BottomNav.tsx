"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { alertCount } from "@/lib/alerts";
import { useSettings } from "@/lib/settings";
import type { AppConfig, Brief } from "@/lib/types";
import { useJson } from "@/lib/useJson";

type Item = { label: string; href: string | null; icon: ReactNode };

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="size-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const ITEMS: Item[] = [
  {
    label: "Brief",
    href: "/",
    icon: (
      <Icon>
        <path d="M4 6h16M4 12h16M4 18h10" />
      </Icon>
    ),
  },
  {
    label: "Alerts",
    href: "/alerts",
    icon: (
      <Icon>
        <path d="M12 3a6 6 0 0 0-6 6v4l-2 3h16l-2-3V9a6 6 0 0 0-6-6zM10 19a2 2 0 0 0 4 0" />
      </Icon>
    ),
  },
  {
    label: "Research",
    href: null, // built in a later step
    icon: (
      <Icon>
        <circle cx="11" cy="11" r="6" />
        <path d="M20 20l-4.5-4.5" />
      </Icon>
    ),
  },
  {
    label: "Settings",
    href: "/settings",
    icon: (
      <Icon>
        <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
        <circle cx="15" cy="7" r="2" />
        <circle cx="9" cy="17" r="2" />
      </Icon>
    ),
  },
];

/** Thumb-zone navigation. The Alerts tab shows how many alerts the user's own lines produce right now. */
export function BottomNav() {
  const pathname = usePathname();
  const brief = useJson<Brief>("/data/brief.json");
  const config = useJson<AppConfig>("/data/config.json");
  const settings = useSettings(config.kind === "ready" ? config.data : null);
  const alerts = brief.kind === "ready" ? alertCount(brief.data, settings) : 0;

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 mx-auto w-full max-w-[430px] border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="grid grid-cols-4">
        {ITEMS.map((item) => {
          const base = "flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs";
          if (!item.href) {
            return (
              <li key={item.label}>
                <span aria-disabled="true" className={`${base} font-medium text-ink-faint opacity-60`}>
                  {item.icon}
                  {item.label}
                </span>
              </li>
            );
          }
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const showBadge = item.label === "Alerts" && alerts > 0;
          return (
            <li key={item.label}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                aria-label={showBadge ? `Alerts, ${alerts} now` : undefined}
                className={`${base} ${active ? "font-semibold text-ink" : "font-medium text-ink-faint"}`}
              >
                <span className="relative">
                  {item.icon}
                  {showBadge && (
                    <span
                      aria-hidden="true"
                      className="absolute -right-2.5 -top-1 min-w-4 rounded-full bg-ink px-1 text-center text-[10px] font-semibold leading-4 text-surface"
                    >
                      {alerts > 9 ? "9+" : alerts}
                    </span>
                  )}
                </span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
