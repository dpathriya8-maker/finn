/** "₹1,339.70" with Indian digit grouping. */
export function formatPrice(value: number): string {
  return "₹" + new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

/** Share counts the way Indian markets say them: "13.8 lakh", "1.25 crore". */
export function formatShares(count: number): string {
  if (count >= 10_000_000) return `${(count / 10_000_000).toFixed(2)} crore`;
  if (count >= 100_000) return `${(count / 100_000).toFixed(1)} lakh`;
  return new Intl.NumberFormat("en-IN").format(count);
}

/** "▲ 5.3%" or "▼ 5.3%"; a flat day has no arrow. */
export function formatMove(changePct: number): string {
  const arrow = changePct > 0 ? "▲ " : changePct < 0 ? "▼ " : "";
  return `${arrow}${Math.abs(changePct).toFixed(1)}%`;
}

/** "Fri 13 Nov" for a trading day written as YYYY-MM-DD. */
export function formatDay(day: string): string {
  const date = new Date(`${day}T12:00:00+05:30`);
  if (Number.isNaN(date.getTime())) return day;
  return new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", weekday: "short", day: "numeric", month: "short" })
    .format(date)
    .replace(",", "");
}

/** "15 Nov, 1:30 am IST" for an ISO timestamp; "an unknown time" if it cannot be parsed. */
export function formatIst(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "an unknown time";
  const text = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);
  return `${text} IST`;
}
