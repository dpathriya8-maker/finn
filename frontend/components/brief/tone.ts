// Full class names so Tailwind can see them. Colour carries meaning only: red bad, amber watch, green good.
// Every coloured card also gets a text tag, so colour is never the only signal.
export const TONE = {
  bad: { border: "border-l-bad", chip: "bg-bad-bg text-bad", tag: "Risk", text: "text-bad" },
  watch: { border: "border-l-watch", chip: "bg-watch-bg text-watch", tag: "Watch", text: "text-watch" },
  good: { border: "border-l-good", chip: "bg-good-bg text-good", tag: "Good news", text: "text-good" },
  neutral: { border: "border-l-line", chip: "", tag: "", text: "text-ink" },
} as const;

export type Tone = keyof typeof TONE;
