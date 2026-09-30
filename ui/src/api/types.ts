export type Lang = { code: string; name: string; status: "supported" | "planned"; reading_rtl?: boolean };

export type SeriesSettings = {
  name: string;
  format: "page" | "scroll";
  source_lang: string;
  target_lang: string;
  created: string;
};

export type ShelfItem = {
  name: string;
  settings: SeriesSettings;
  episodes: number;
  pages: number;
  done_pages: number;
  pending_terms: number;
  cover: string | null;
};

export type PageStatus = "new" | "ocr" | "translated" | "done";

export type EpisodeSummary = {
  id: string;
  label: string;
  pages: number;
  counts: Record<PageStatus, number>;
  status: "empty" | "todo" | "partial" | "done";
};

export type EpisodePage = {
  stem: string;
  status: PageStatus;
  regions: number;
  translated_regions: number;
  original: string;
  /** 譯圖網址；還沒嵌字時是 null */
  translated: string | null;
  thumb: string;
};

export type Job = {
  id: string;
  series: string;
  episode: string;
  steps: string[];
  force: boolean;
  status: "queued" | "running" | "done" | "error";
  step: string | null;
  log: string[];
  warnings: string[];
  new_terms: number;
  error: string | null;
  created: number;
  finished: number | null;
};

export type EpisodeDetail = EpisodeSummary & { pages_detail: EpisodePage[]; job: Job | null };

export type SeriesDetail = {
  name: string;
  settings: SeriesSettings;
  episodes: EpisodeSummary[];
  glossary: { confirmed: number; pending: number };
  cover: string | null;
  jobs: Job[];
};

export type Term = {
  source: string;
  target: string;
  category: "character" | "place" | "technique" | "item" | "other";
  status: "confirmed" | "pending";
  note: string;
  first_seen: string;
  thumb: string | null;
};

export type Glossary = { target_lang: string; terms: Term[] };

export type Notes = { rules: string; summary: string };

export type AssetInfo = {
  id: string;
  purpose: string;
  purpose_en: string;
  size: [number, number];
  background: "transparent" | "opaque";
  source: "default" | "custom";
  format: string;
  pixel_size: [number, number] | null;
  warnings: string[];
  url: string;
};

export type Status = {
  version: string;
  gpu: { cuda: boolean; name: string | null; vram_gb: number | null; device: string | null };
  claude: { installed: boolean; version: string | null; logged_in: boolean | null; subscription: string | null };
  data_home: string;
  models_dir: string;
  languages: { sources: Lang[]; targets: Lang[] };
};
