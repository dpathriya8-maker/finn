import { effectiveLabel, kindLabel, lacksProfile, movement, termLabel } from "@/lib/management";
import type { ManagementCard } from "@/lib/types";

const MOVEMENT_CHIP: Record<string, string> = {
  Leaving: "bg-watch-bg text-watch",
  Joining: "bg-good-bg text-good",
  Continuing: "bg-backdrop text-ink-soft",
  "New role": "bg-backdrop text-ink-soft",
};

/** Who is involved in a management change, from the filing itself: name, role, from when, and its own profile of them. */
export function ManagementCardView({ card }: { card: ManagementCard }) {
  if (card.status === "failed") {
    return (
      <div role="note" className="rounded-xl border border-line bg-backdrop px-3 py-2.5 text-sm leading-6 text-ink-soft">
        <p className="font-medium text-ink">Details not shown</p>
        <p>{card.reason}</p>
      </div>
    );
  }
  if (card.people.length === 0) {
    return (
      <div role="note" className="rounded-xl border border-line bg-backdrop px-3 py-2.5 text-sm leading-6 text-ink-soft">
        <p className="font-medium text-ink">Details not shown</p>
        {card.warnings.map((warning) => (
          <p key={warning}>{warning}</p>
        ))}
      </div>
    );
  }

  return (
    <section aria-label="Management change" className="space-y-4 text-sm">
      {card.people.map((person) => {
        const move = movement(person);
        const effective = effectiveLabel(person);
        const term = termLabel(person);
        return (
          <div key={person.name} className="space-y-2">
            <p className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="font-medium text-ink-faint">{kindLabel(person.kind)}</span>
              {move && <span className={`rounded px-1.5 py-0.5 font-medium ${MOVEMENT_CHIP[move] ?? "bg-backdrop text-ink-soft"}`}>{move}</span>}
            </p>
            <div>
              <h3 className="text-base font-semibold leading-snug">{person.name}</h3>
              <p className="mt-0.5 leading-6 text-ink-soft">{person.role}</p>
            </div>
            {(effective || term || person.din) && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs leading-5">
                {effective && (
                  <>
                    <dt className="text-ink-faint">Effective</dt>
                    <dd className="font-medium">
                      {effective}
                      {term ? ` · ${term}` : ""}
                    </dd>
                  </>
                )}
                {!effective && term && (
                  <>
                    <dt className="text-ink-faint">Term</dt>
                    <dd className="font-medium">{term}</dd>
                  </>
                )}
                {person.din && (
                  <>
                    <dt className="text-ink-faint">DIN</dt>
                    <dd className="font-medium tabular-nums">{person.din}</dd>
                  </>
                )}
              </dl>
            )}
            {person.profile && (
              <figure className="rounded-xl bg-backdrop px-3 py-2.5">
                <figcaption className="text-xs font-medium text-ink-faint">The filing’s own profile (page {person.profile.page})</figcaption>
                <blockquote className="mt-1 text-sm leading-6 text-ink-soft">{person.profile.text}</blockquote>
              </figure>
            )}
            {lacksProfile(person) && <p className="text-xs leading-5 text-ink-faint">The filing does not include a profile for them.</p>}
          </div>
        );
      })}
      <p className="text-xs leading-5 text-ink-faint">
        Read from the filing{card.source.pages.length ? ` (${card.source.pages.length === 1 ? "page" : "pages"} ${card.source.pages.join(", ")})` : ""}, not written by a model.
      </p>
    </section>
  );
}
