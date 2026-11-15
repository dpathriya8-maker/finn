/** Marks anything that is a concept and not connected to real data or a real service. Never hidden, never subtle. */
export function PreviewBadge({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border border-watch px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-watch ${className}`}>
      Preview
    </span>
  );
}
