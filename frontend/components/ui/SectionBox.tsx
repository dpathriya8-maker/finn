import { useId, type ReactNode } from "react";

/**
 * A section of the Brief or the Interested tab: a soft rounded box with a clear header (title, a small count, one line saying what
 * it is) and the cards inside it. The padding is the same everywhere, so every section lines up. The cards stay white on the box.
 * `bare` keeps the header and the spacing but drops the box, for a section that sits inside another.
 */
export function SectionBox({
  title,
  count,
  hint,
  bare = false,
  className = "",
  children,
}: {
  title: string;
  count?: string;
  hint?: string;
  bare?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const id = useId();
  const Heading = bare ? "h3" : "h2";
  return (
    <section aria-labelledby={id} className={`min-w-0 ${bare ? "" : "rounded-3xl bg-section p-2.5"} ${className}`}>
      <header className={bare ? "" : "px-1.5 pb-2.5 pt-1.5"}>
        <Heading id={id} className="flex items-baseline gap-2 text-sm font-semibold">
          {title}
          {count && <span className="text-xs font-normal text-ink-faint">{count}</span>}
        </Heading>
        {hint && <p className="mt-0.5 text-xs leading-5 text-ink-faint">{hint}</p>}
      </header>
      <div className={`flex flex-col gap-2.5 ${bare ? "mt-3" : ""}`}>{children}</div>
    </section>
  );
}
