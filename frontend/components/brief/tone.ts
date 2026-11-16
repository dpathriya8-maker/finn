// Full class names so Tailwind can see them. Colour carries meaning only: red bad, amber watch, green good.
// Every coloured card also gets a text tag, so colour is never the only signal. `tint` is a soft wash of the colour over the card
// (about 9% in light mode, 16% in dark); `border` is the 3px left edge in the full colour. Neutral and routine cards have neither.
// `chip` is the tag on a plain card; `chipOnTint` is the same tag on a tinted card, where a second fill on top of the tint would
// make the coloured word unreadable in dark mode, so it sits on the plain surface with a thin ring in the status colour.
export const TONE = {
  bad: { border: "border-l-bad", tint: "bg-bad-tint", chip: "bg-bad-bg text-bad", chipOnTint: "bg-surface text-bad ring-1 ring-inset ring-bad/35", tag: "Risk", text: "text-bad" },
  watch: { border: "border-l-watch", tint: "bg-watch-tint", chip: "bg-watch-bg text-watch", chipOnTint: "bg-surface text-watch ring-1 ring-inset ring-watch/35", tag: "Watch", text: "text-watch" },
  good: { border: "border-l-good", tint: "bg-good-tint", chip: "bg-good-bg text-good", chipOnTint: "bg-surface text-good ring-1 ring-inset ring-good/35", tag: "Good", text: "text-good" },
  neutral: { border: "border-l-line", tint: "", chip: "", chipOnTint: "", tag: "", text: "text-ink" },
} as const;

export type Tone = keyof typeof TONE;

/**
 * The look of a card by its tone: a 3px left edge and a soft tint in the status colour, or, for a neutral card, no tint and a
 * transparent edge (so the text does not shift). Pass `plain` for the background a neutral card should have.
 */
export function toneBox(tone: Tone, plain = ""): string {
  return tone === "neutral" ? `border-l-[3px] border-l-transparent ${plain}`.trim() : `border-l-[3px] ${TONE[tone].border} ${TONE[tone].tint}`;
}
