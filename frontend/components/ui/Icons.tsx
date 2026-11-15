import type { ReactNode } from "react";

/** Small line icons, drawn here as inline SVG (no icon library). One stroke width everywhere so they read as a set. */
function Svg({ children, size = 16, label }: { children: ReactNode; size?: number; label?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className="shrink-0"
    >
      {children}
    </svg>
  );
}

type IconProps = { size?: number; label?: string };

export const BarChartIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 20V10M12 20V4M19 20v-7" />
  </Svg>
);
export const PersonIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" />
  </Svg>
);
export const ArrowsIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 8h13l-3-3M20 16H7l3 3" />
  </Svg>
);
export const BriefcaseIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.5" y="7.5" width="17" height="12" rx="2" />
    <path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5M3.5 12.5h17" />
  </Svg>
);
export const GavelIcon = (p: IconProps) => (
  <Svg {...p}>
    <g transform="rotate(-45 12 11)">
      <rect x="7.5" y="3" width="9" height="5.5" rx="1" />
      <path d="M12 8.5v9" />
    </g>
    <path d="M5 21h9" />
  </Svg>
);
export const ShieldIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
    <path d="M9 12l2 2 4-4" />
  </Svg>
);
export const CoinIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9 9h6M9 12h6M10 9c3 0 4 1.2 4 3s-1.5 2.6-4 2.6l4 3.4" />
  </Svg>
);
export const LockIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="5" y="10.5" width="14" height="10" rx="2" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
  </Svg>
);
export const FileIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 3.5h7l4 4v13H7z" />
    <path d="M14 3.5v4h4" />
  </Svg>
);
export const BuildingIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 20V9l6 3V9l6 3V5h4v15z" />
  </Svg>
);
export const MegaphoneIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 10v4h3l6 4V6L7 10z" />
    <path d="M16 9a4 4 0 0 1 0 6" />
  </Svg>
);
export const SlidersIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
    <circle cx="16" cy="7" r="2" />
    <circle cx="8" cy="17" r="2" />
  </Svg>
);
export const StarIcon = ({ filled, ...p }: IconProps & { filled?: boolean }) => (
  <svg viewBox="0 0 24 24" width={p.size ?? 18} height={p.size ?? 18} fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.75} strokeLinejoin="round" aria-hidden="true" className="shrink-0">
    <path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.7l5.9-.8z" />
  </svg>
);
export const CloseIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Svg>
);

/** One icon per category id (config/categories.json); routine filings and anything unknown get the plain file. */
export function CategoryIcon({ category, routine, size = 14 }: { category: string; routine?: boolean; size?: number }) {
  if (routine) return <FileIcon size={size} />;
  switch (category) {
    case "results":
      return <BarChartIcon size={size} />;
    case "management_change":
      return <PersonIcon size={size} />;
    case "m_and_a":
      return <ArrowsIcon size={size} />;
    case "fund_raise":
      return <BriefcaseIcon size={size} />;
    case "litigation":
      return <GavelIcon size={size} />;
    case "credit_rating":
      return <ShieldIcon size={size} />;
    case "dividend":
    case "bonus_split":
      return <CoinIcon size={size} />;
    case "pledging":
      return <LockIcon size={size} />;
    case "capex":
      return <BuildingIcon size={size} />;
    case "press_release":
      return <MegaphoneIcon size={size} />;
    default:
      return <FileIcon size={size} />;
  }
}
