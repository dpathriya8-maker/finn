import Link from "next/link";
import type { ReactNode } from "react";

type Item = { label: string; href?: string; icon: ReactNode };

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
    icon: (
      <Icon>
        <path d="M12 3a6 6 0 0 0-6 6v4l-2 3h16l-2-3V9a6 6 0 0 0-6-6zM10 19a2 2 0 0 0 4 0" />
      </Icon>
    ),
  },
  {
    label: "Research",
    icon: (
      <Icon>
        <circle cx="11" cy="11" r="6" />
        <path d="M20 20l-4.5-4.5" />
      </Icon>
    ),
  },
  {
    label: "Settings",
    icon: (
      <Icon>
        <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
        <circle cx="15" cy="7" r="2" />
        <circle cx="9" cy="17" r="2" />
      </Icon>
    ),
  },
];

/** Thumb-zone navigation. Only the Brief tab exists so far; the others are placeholders. */
export function BottomNav() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 mx-auto w-full max-w-[430px] border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="grid grid-cols-4">
        {ITEMS.map((item) => {
          const base = "flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs";
          return (
            <li key={item.label}>
              {item.href ? (
                <Link href={item.href} aria-current="page" className={`${base} font-semibold text-ink`}>
                  {item.icon}
                  {item.label}
                </Link>
              ) : (
                <span aria-disabled="true" className={`${base} font-medium text-ink-faint opacity-60`}>
                  {item.icon}
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
