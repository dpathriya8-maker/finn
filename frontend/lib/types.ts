/** Shapes of the static JSON the pipeline writes to public/data/. Mirrors backend/app/push/digest.py. */

export type Item = {
  id: string;
  symbol: string;
  company: string;
  source: "bse" | "nse";
  published_at: string; // ISO, India time
  /** One of the 17 category ids in config/categories.json, for example "results" or "litigation". */
  category: string;
  category_label: string;
  card_type: "results" | "management" | "one_liner" | "surface_only";
  /** 0-100, higher is shown first. Risks outrank good news. */
  priority: number;
  /** Collapsed into the "N routine filings" row. */
  routine: boolean;
  /** Whether this category pushes an alert unless the user turns it off. */
  default_alert: boolean;
  /** One line explaining the rank, for example "A key person is leaving: exits rank above hires". */
  why: string;
  /** One-line headline built by rules (not a model). */
  headline: string;
  /** Which classification rule decided, so it can be audited. */
  rule: string;
  /** How many duplicate filings of the same results were folded into this one. */
  merged?: number;
  subject: string;
  body: string;
  raw_category: string;
  raw_subcategory: string;
  url: string | null;
  size_kb: number | null;
};

export type Session = {
  day: string;
  close: number;
  prev_close: number;
  change_pct: number;
  volume: number;
  avg_volume: number | null;
  volume_ratio: number | null;
};

export type BriefCompany = {
  symbol: string;
  name: string;
  sector: string;
  size_bucket: string;
  /** Parts that failed this run and are showing older data: part name to when that data was produced. */
  stale: Record<string, string>;
  errors: Record<string, string>;
};

export type Brief = {
  schema: number;
  generated_at: string;
  item_days: number;
  companies: BriefCompany[];
  items: Item[];
  signals: { symbol: string; sessions: Session[] }[];
};
