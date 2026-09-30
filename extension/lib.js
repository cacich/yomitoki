// 插件共用的純函式：不依賴 chrome.* API，可以直接用 node --test 測試。

export const SERVER = "http://127.0.0.1:8765";

// 本機伺服器要求會改變資料的請求都帶這個標頭（防止其他網站跨站呼叫）
export const CLIENT_HEADERS = { "X-Yomitoki-Client": "extension" };

const enc = encodeURIComponent;

export function translateUrl({ series, episode } = {}) {
  const url = new URL("/translate", SERVER);
  if (series) url.searchParams.set("series", series);
  if (series && episode) url.searchParams.set("episode", episode);
  return url.toString();
}

export const seriesListUrl = () => `${SERVER}/api/series`;
export const seriesUrl = (series) => `${SERVER}/api/series/${enc(series)}`;
export const createEpisodeUrl = (series) => `${seriesUrl(series)}/episodes`;
export const uploadUrl = (series, episode) => `${seriesUrl(series)}/episodes/${episode}/pages`;
export const healthUrl = () => `${SERVER}/health`;
export const assetUrl = (id) => `${SERVER}/api/assets/${id}/file`;
export const appUrl = () => `${SERVER}/`;

export function readerUrl(series, episode, stem) {
  const base = `${SERVER}/read/${enc(series)}/${episode}`;
  return stem ? `${base}/${stem}` : base;
}

/** 伺服器把警告等資訊以「URL 編碼的 JSON」放在回應標頭裡。 */
export function parseHeaderJson(value, fallback) {
  if (!value) return fallback;
  try {
    return JSON.parse(decodeURIComponent(value));
  } catch {
    return fallback;
  }
}

/** 把 /translate 的回應標頭整理成側邊面板要顯示的資訊。 */
export function translateMeta(headers) {
  const get = (name) => (typeof headers.get === "function" ? headers.get(name) : headers[name]);
  const seconds = parseHeaderJson(get("x-yomitoki-seconds"), {});
  const total = Object.values(seconds).reduce((a, b) => a + (Number(b) || 0), 0);
  return {
    regions: Number(get("x-yomitoki-regions") ?? 0),
    newTerms: Number(get("x-yomitoki-new-terms") ?? 0),
    warnings: parseHeaderJson(get("x-yomitoki-warnings"), []),
    seconds: Math.round(total * 10) / 10,
  };
}

/**
 * 把錯誤轉成 { key, detail }：key 是 _locales 裡的訊息代號。
 * status 為 0 代表連線失敗（伺服器沒啟動）。
 */
export function describeError(status, detail = "") {
  if (status === 0) return { key: "errServerDown", detail };
  if (status === 401) return { key: "errClaudeLogin", detail };
  if (status === 503) return { key: "errClaudeMissing", detail };
  return { key: "errGeneric", detail: detail || `HTTP ${status}` };
}

export async function readErrorDetail(response) {
  try {
    const data = await response.json();
    return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
  } catch {
    return response.statusText;
  }
}

/** 話數資料夾 ep012 → 12；非數字的話數原樣顯示。 */
export function episodeNumber(id) {
  const rest = String(id).replace(/^ep/, "");
  return /^\d+$/.test(rest) ? String(Number(rest)) : rest;
}

/** 選單預設選最後一話（最新的一話通常就是正在讀的）。 */
export function pickEpisode(episodes, preferred) {
  if (!episodes?.length) return null;
  if (preferred && episodes.some((e) => e.id === preferred)) return preferred;
  return episodes[episodes.length - 1].id;
}

/** 這些網址 Chrome 不允許擷取畫面。 */
export function isCapturable(url) {
  if (!url) return false;
  return !/^(chrome|chrome-extension|edge|about|devtools|view-source):/i.test(url) &&
    !/^https:\/\/chromewebstore\.google\.com\//i.test(url) &&
    !/^https:\/\/chrome\.google\.com\/webstore/i.test(url);
}

export function dataUrlToBlob(dataUrl) {
  const [head, body] = dataUrl.split(",");
  const mime = /data:([^;]+)/.exec(head)?.[1] ?? "application/octet-stream";
  const bytes = Uint8Array.from(atob(body), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: mime });
}

export async function blobToDataUrl(blob) {
  const buf = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < buf.length; i += 0x8000) binary += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return `data:${blob.type || "image/png"};base64,${btoa(binary)}`;
}
