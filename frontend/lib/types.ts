/** Shapes of the static JSON the pipeline writes to public/data/. Mirrors backend/app/push/digest.py. */

export type Item = {
  id: string;
  symbol: string;
  company: string;
  source: "bse" | "nse";
  published_at: string; // ISO, India time
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
