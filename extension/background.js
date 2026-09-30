// Yomitoki 插件的背景程式（service worker）。
//
// 界線：
// - 只用 chrome.tabs.captureVisibleTab 擷取「畫面上看得到的內容」，
//   不下載、不攔截、不讀取網頁裡的圖片，也沒有任何針對特定網站的程式碼。
// - 截圖一律由使用者觸發（快捷鍵、工具列圖示或側邊面板的按鈕），不自動翻頁、不自動捲動。

import {
  CLIENT_HEADERS,
  blobToDataUrl,
  dataUrlToBlob,
  describeError,
  isCapturable,
  readErrorDetail,
  translateMeta,
  translateUrl,
  uploadUrl,
} from "./lib.js";

const DEFAULT_SETTINGS = { series: "", episode: "", mode: "translate" };
const WORKING_STATES = new Set(["capturing", "translating", "saving"]);
const REQUEST_TIMEOUT_MS = 5 * 60 * 1000;
// 截圖高度低於這個值時，對話框裡的字通常太小，OCR 容易出錯
const SMALL_CAPTURE_PX = 1000;

// Chrome 約 30 秒沒有事件就會關掉 service worker，即使它還在等 fetch 的回應。
// 翻譯一頁常常超過 30 秒，所以工作進行中每 20 秒呼叫一次插件 API，讓它保持清醒。
function keepAlive() {
  const timer = setInterval(() => chrome.runtime.getPlatformInfo(), 20_000);
  return () => clearInterval(timer);
}

// service worker 重新啟動時，上一個實例裡的工作已經中斷；不要讓面板永遠停在「翻譯中」
chrome.storage.session.get("job").then(({ job }) => {
  if (job && WORKING_STATES.has(job.state)) {
    chrome.storage.session.set({ job: { ...job, state: "error", error: { key: "errInterrupted", detail: "" } } });
  }
});

// 點工具列圖示時直接打開側邊面板
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

chrome.commands.onCommand.addListener((command, tab) => {
  if (command !== "capture" || !tab) return;
  // 側邊面板只能在使用者操作的當下打開，所以要在任何 await 之前呼叫
  chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
  captureAndProcess(tab);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "capture") return false;
  chrome.tabs.query({ active: true, lastFocusedWindow: true }).then(([tab]) => {
    if (tab) captureAndProcess(tab);
    sendResponse({ ok: !!tab });
  });
  return true;
});

async function getSettings() {
  const { settings } = await chrome.storage.local.get("settings");
  return { ...DEFAULT_SETTINGS, ...(settings ?? {}) };
}

let latestJobId = 0;

/** 只保留最新一次截圖的狀態；較舊的工作晚回來時不會蓋掉畫面。 */
async function setJob(id, patch) {
  if (id < latestJobId) return;
  const { job } = await chrome.storage.session.get("job");
  const next = { ...(job?.id === id ? job : {}), id, ...patch };
  try {
    await chrome.storage.session.set({ job: next });
  } catch {
    // 圖太大放不進 session storage 時，至少保留譯圖
    delete next.original;
    await chrome.storage.session.set({ job: next }).catch(() => {});
  }
}

async function fail(id, key, detail = "") {
  await setJob(id, { state: "error", error: { key, detail } });
}

async function captureAndProcess(tab) {
  const release = keepAlive();
  try {
    await runCapture(tab);
  } finally {
    release();
  }
}

async function runCapture(tab) {
  const id = Date.now();
  latestJobId = id;
  const settings = await getSettings();
  await chrome.storage.session.set({ job: { id, state: "capturing", mode: settings.mode, startedAt: id } });

  if (tab.url && !isCapturable(tab.url)) return fail(id, "errCapture");

  let dataUrl;
  try {
    dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  } catch (e) {
    const permission = /permission|activeTab|all_urls/i.test(String(e?.message ?? e));
    return fail(id, permission ? "captureNeedsShortcut" : "errCapture", String(e?.message ?? e));
  }
  const png = dataUrlToBlob(dataUrl);
  const original = await toDisplayDataUrl(png);
  const size = await imageSize(png);
  const small = size && size.height < SMALL_CAPTURE_PX ? size : null;

  if (settings.mode === "save") {
    if (!settings.series || !settings.episode) return fail(id, "modeSaveNeedsSeries");
    await setJob(id, { state: "saving", original });
    const form = new FormData();
    form.append("files", png, "screenshot.png");
    const res = await post(uploadUrl(settings.series, settings.episode), form);
    if (!res.ok) return fail(id, res.error.key, res.error.detail);
    const { saved } = await res.response.json();
    return setJob(id, { state: "saved", small, saved: { series: settings.series, episode: settings.episode, page: saved[0] } });
  }

  await setJob(id, { state: "translating", original, small });
  const res = await post(translateUrl(settings), png, { "Content-Type": "image/png" });
  if (!res.ok) return fail(id, res.error.key, res.error.detail);
  const meta = translateMeta(res.response.headers);
  const episode = res.response.headers.get("x-yomitoki-episode");
  const page = res.response.headers.get("x-yomitoki-page");
  const result = await toDisplayDataUrl(await res.response.blob());
  await setJob(id, {
    state: "done",
    result,
    meta,
    saved: episode && page ? { series: settings.series, episode, page } : null,
  });
}

async function post(url, body, headers = {}) {
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      body,
      headers: { ...CLIENT_HEADERS, ...headers },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (e) {
    if (e?.name === "TimeoutError") return { ok: false, error: { key: "errTimeout", detail: "" } };
    return { ok: false, error: describeError(0, String(e?.message ?? e)) };
  }
  if (!response.ok) return { ok: false, error: describeError(response.status, await readErrorDetail(response)) };
  return { ok: true, response };
}

async function imageSize(blob) {
  try {
    const bitmap = await createImageBitmap(blob);
    const size = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return size;
  } catch {
    return null;
  }
}

/** 側邊面板顯示用：轉成 JPEG 以節省 session storage 空間；失敗就保留原格式。 */
async function toDisplayDataUrl(blob) {
  try {
    const bitmap = await createImageBitmap(blob);
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    canvas.getContext("2d").drawImage(bitmap, 0, 0);
    bitmap.close();
    return await blobToDataUrl(await canvas.convertToBlob({ type: "image/jpeg", quality: 0.9 }));
  } catch {
    return blobToDataUrl(blob);
  }
}
