"use client";

/** A whole row you can tap, with a switch on the right. Large touch target; the row text is its accessible name. */
export function SwitchRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex min-h-14 w-full items-center justify-between gap-4 px-4 py-2 text-left"
    >
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        {hint && <span className="block text-xs leading-5 text-ink-faint">{hint}</span>}
      </span>
      <span
        aria-hidden="true"
        className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors motion-reduce:transition-none ${
          checked ? "bg-ink" : "bg-line"
        }`}
      >
        <span
          className={`absolute size-5 rounded-full shadow transition-transform motion-reduce:transition-none ${
            checked ? "translate-x-6 bg-surface" : "translate-x-1 bg-ink-faint"
          }`}
        />
      </span>
    </button>
  );
}

/** A labelled slider with its current value, its range and its default shown, so nothing is a guess. */
export function RangeSetting({
  id,
  label,
  unit,
  min,
  max,
  step,
  value,
  defaultValue,
  hint,
  onChange,
}: {
  id: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
  value: number;
  defaultValue: number;
  hint: string;
  onChange: (next: number) => void;
}) {
  return (
    <div className="px-4 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <output htmlFor={id} className="text-base font-semibold tabular-nums">
          {value}
          {unit}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={`${value}${unit}`}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 h-11 w-full accent-[var(--ink)]"
      />
      <div className="flex justify-between text-xs tabular-nums text-ink-faint">
        <span>
          {min}
          {unit}
        </span>
        <span>
          default {defaultValue}
          {unit}
        </span>
        <span>
          {max}
          {unit}
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-ink-soft">{hint}</p>
    </div>
  );
}
