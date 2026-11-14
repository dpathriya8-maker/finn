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
  /** The only thing the app may colour: bad is red, watch is amber, good is green, neutral has no colour. */
  tone: "bad" | "watch" | "good" | "neutral";
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
  /** Present on results and management filings the pipeline could look into. Absent means no attempt was made. */
  card?: Card;
};

/** One line of the results table. Changes are computed by the pipeline from the printed figures, never by a model. */
export type CardMetric = {
  key: "revenue" | "ebitda" | "pbt" | "pat" | "pat_owners";
  label: string;
  /** Rupees crore (converted by the pipeline from crore, lakh or million as printed). Null if it could not be read. */
  current: number | null;
  previous: number | null;
  year_ago: number | null;
  qoq_pct: number | null;
  yoy_pct: number | null;
  /** When a percentage means nothing (loss to profit or back), the change is named instead. */
  qoq_swing: "turned profit" | "turned loss" | null;
  yoy_swing: "turned profit" | "turned loss" | null;
  /** Where in the filing the figures were read. Tokens are exactly as printed; null where none is printed. */
  printed: { label: string; page: number; tokens: (string | null)[] };
  /** Set when the figure is computed here and not printed, with how. */
  derived?: string;
};

export type CardCheck = {
  status: "ok" | "differs" | "unavailable";
  against: string;
  note: string;
  /** What was compared, in rupees crore: present unless nothing could be compared. */
  details?: { metric: "revenue" | "pbt" | "pat"; filing: number; yahoo: number; diff_pct: number; ok: boolean }[];
};

export type ResultsCard =
  | { type: "results"; status: "failed"; reason: string; extractor: string }
  | {
      type: "results";
      status: "ok" | "partial";
      /** Set for scanned filings, whose figures are shown only where an independent source agrees. */
      verification: string | null;
      basis: "consolidated" | "standalone" | "not stated";
      unit_printed: string | null;
      period: { label: string; current: string | null; previous: string | null; year_ago: string | null };
      source: { url: string | null; pages: number[] };
      metrics: CardMetric[];
      margins: Record<string, { current: number | null; year_ago: number | null }>;
      warnings: string[];
      check: CardCheck;
      tone: "bad" | "watch" | "good" | "neutral";
      tone_reason: string;
      extractor: string;
    };

/** One person in a management-change filing. Every field is a literal piece of the filing, found by rules. */
export type ManagementPerson = {
  name: string;
  din: string | null;
  role: string;
  /** appointment, re-appointment, redesignation, resignation, retirement, cessation, death, removal, or change. */
  kind: string;
  direction: "in" | "out" | "";
  effective: { date: string; text: string } | null;
  term: string | null;
  /** The filing's own "profile" section, word for word. Null if it has none. */
  profile: { text: string; page: number; source: "filing" } | null;
  page: number | null;
};

export type ManagementCard =
  | { type: "management"; status: "failed"; reason: string; extractor: string }
  | {
      type: "management";
      status: "ok" | "partial";
      kind: string;
      direction: "in" | "out" | "";
      /** Empty when the filing's text did not let anyone be named: the card then says so and claims nothing more. */
      people: ManagementPerson[];
      source: { url: string | null; pages: number[] };
      warnings: string[];
      extractor: string;
    };

export type Card = ResultsCard | ManagementCard;

export type Session = {
  day: string;
  close: number;
  prev_close: number;
  change_pct: number;
  volume: number;
  avg_volume: number | null;
  volume_ratio: number | null;
};

/** config.json: the pipeline copies config/defaults.json and config/categories.json here. */
export type AppConfig = {
  schema: number;
  defaults: { window_hours: number; volume_multiple: number; price_move_pct: number; volume_lookback_days: number };
  categories: {
    id: string;
    label: string;
    why: string;
    weight: number;
    is_routine: boolean;
    default_alert: boolean;
    card_type: string;
  }[];
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
