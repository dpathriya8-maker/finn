/** Marks anything that is a concept and not connected to real data or a real service. Never hidden, never subtle. */
export function PreviewBadge({ className = "", onAccent = false }: { className?: string; onAccent?: boolean }) {
  // On an indigo button the amber badge would be unreadable, so it takes the button's own text colour instead.
  const colours = onAccent ? "border-on-accent text-on-accent" : "border-watch text-watch";
  return (
    <span className={`inline-flex items-center rounded-full border px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide ${colours} ${className}`}>
      Preview
    </span>
  );
}
