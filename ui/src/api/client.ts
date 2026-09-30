import type {
  AssetInfo,
  EpisodeDetail,
  EpisodeSummary,
  Glossary,
  Job,
  Notes,
  SeriesDetail,
  ShelfItem,
  Status,
  Term,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// 伺服器要求會改變資料的請求都帶這個標頭（防止其他網站跨站呼叫本機 API）
const CLIENT_HEADER = { "X-Yomitoki-Client": "ui" };

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: method === "GET" ? {} : { ...CLIENT_HEADER } };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* 不是 JSON 就用 statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const s = (name: string) => `/api/series/${encodeURIComponent(name)}`;

export const api = {
  status: () => request<Status>("GET", "/api/status"),

  shelf: () => request<ShelfItem[]>("GET", "/api/series"),
  createSeries: (body: { name: string; format: string; source_lang: string; target_lang: string }) =>
    request<{ name: string }>("POST", "/api/series", body),
  series: (name: string) => request<SeriesDetail>("GET", s(name)),

  createEpisode: (name: string) => request<EpisodeSummary>("POST", `${s(name)}/episodes`, {}),
  episode: (name: string, ep: string) => request<EpisodeDetail>("GET", `${s(name)}/episodes/${ep}`),
  uploadPages: (name: string, ep: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f, f.name));
    return request<{ saved: string[] }>("POST", `${s(name)}/episodes/${ep}/pages`, form);
  },
  run: (name: string, ep: string, steps: string[], force = false) =>
    request<Job>("POST", `${s(name)}/episodes/${ep}/run`, { steps, force }),
  job: (id: string) => request<Job>("GET", `/api/jobs/${id}`),

  glossary: (name: string) => request<Glossary>("GET", `${s(name)}/glossary`),
  setTerm: (name: string, t: Pick<Term, "source" | "target"> & Partial<Pick<Term, "category" | "note">>) =>
    request<Glossary>("POST", `${s(name)}/glossary/set`, t),
  confirmTerm: (name: string, source: string, target?: string) =>
    request<Glossary>("POST", `${s(name)}/glossary/confirm`, { source, target }),
  removeTerm: (name: string, source: string) => request<Glossary>("POST", `${s(name)}/glossary/remove`, { source }),
  notes: (name: string) => request<Notes>("GET", `${s(name)}/notes`),
  saveNotes: (name: string, notes: Notes) => request<Notes>("PUT", `${s(name)}/notes`, notes),

  assets: () => request<AssetInfo[]>("GET", "/api/assets"),
  replaceAsset: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return request<AssetInfo[]>("POST", `/api/assets/${id}`, form);
  },
  restoreAsset: (id: string) => request<AssetInfo[]>("DELETE", `/api/assets/${id}`),

  openFolder: (series?: string, episode?: string) =>
    request<{ path: string }>("POST", "/api/open-folder", { series, episode }),
};
