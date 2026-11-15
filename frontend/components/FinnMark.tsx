/**
 * The FINN mark: an indigo rounded square with a white "F" and a small upward tick. Inline SVG, drawn with the theme's accent
 * colours (a light F on deep indigo in light mode; a dark F on soft indigo in dark mode), so it keeps its contrast in both.
 */
export function FinnMark({ size = 28 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden="true" className="shrink-0">
      <rect width="32" height="32" rx="8" fill="var(--accent-bg)" />
      <path d="M9.5 8h11v3.4h-7.6v3.6h5.6v3.3h-5.6V24H9.5z" fill="var(--on-accent)" />
      <path d="M21.6 12.6l3-4 3 4" fill="none" stroke="var(--on-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
