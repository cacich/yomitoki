// 側邊面板：選作品與話數、顯示截圖與翻譯的進度和結果。實際的截圖與送出在 background.js。

import {
  CLIENT_HEADERS,
  appUrl,
  assetUrl,
  createEpisodeUrl,
  episodeNumber,
  healthUrl,
  pickEpisode,
  readerUrl,
  seriesListUrl,
  seriesUrl,
} from "./lib.js";

const $ = (id) => document.getElementById(id);
const msg = (key, subs) => chrome.i18n.getMessage(key, subs) || key;
const DEFAULT_SETTINGS = { series: "", episode: "", mode: "translate" };
const STALE_MS = 6 * 60 * 1000; // 比背景程式的 5 分鐘逾時再多一點

let settings = { ...DEFAULT_SETTINGS };
let shortcut = "";
let connected = false;

// ── 語系與主題 ──────────────────────────────────────────
document.documentElement.lang = chrome.i18n.getUILanguage().startsWith("zh") ? "zh-Hant" : "en";
document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = msg(el.dataset.i18n)));
const dark = matchMedia("(prefers-color-scheme: dark)");
function applyTheme() {
  if (dark.matches) document.documentElement.dataset.theme = "night";
  else delete document.documentElement.dataset.theme;
}
applyTheme();
dark.addEventListener("change", applyTheme);

// ── 設定 ───────────────────────────────────────────────
async function loadSettings() {
  const { settings: saved } = await chrome.storage.local.get("settings");
  settings = { ...DEFAULT_SETTINGS, ...(saved ?? {}) };
}

async function saveSettings(patch) {
  settings = { ...settings, ...patch };
  await chrome.storage.local.set({ settings });
  renderMode();
}

// ── 連線與作品清單 ─────────────────────────────────────
async function getJson(url, init) {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function checkServer() {
  let ok = false;
  try {
    ok = (await getJson(healthUrl())).status === "ok";
  } catch {
    ok = false;
  }
  const changed = ok !== connected;
  connected = ok;
  $("status").dataset.state = ok ? "ok" : "down";
  $("status-text").textContent = msg(ok ? "statusOk" : "statusDown");
  $("down").hidden = ok;
  $("mascot-guide").src = ok ? assetUrl("mascot-guide") : "icons/icon-128.png";
  $("mascot-loading").src = ok ? assetUrl("mascot-loading") : "icons/icon-128.png";
  if (ok && changed) await loadSeries();
}

async function loadSeries() {
  const select = $("series");
  let items = [];
  try {
    items = await getJson(seriesListUrl());
  } catch {
    return;
  }
  select.replaceChildren(new Option(msg("seriesNone"), ""), ...items.map((s) => new Option(s.name, s.name)));
  if (settings.series && !items.some((s) => s.name === settings.series)) await saveSettings({ series: "", episode: "" });
  select.value = settings.series;
  await loadEpisodes();
}

async function loadEpisodes() {
  const row = $("episode-row");
  const select = $("episode");
  if (!settings.series) {
    row.hidden = true;
    return;
  }
  row.hidden = false;
  let episodes = [];
  try {
    episodes = (await getJson(seriesUrl(settings.series))).episodes;
  } catch {
    return;
  }
  select.replaceChildren(
    ...episodes.map((e) => new Option(msg("episodeLabel", [episodeNumber(e.id), String(e.pages)]), e.id)),
  );
  const chosen = pickEpisode(episodes, settings.episode) ?? "";
  select.value = chosen;
  if (chosen !== settings.episode) await saveSettings({ episode: chosen });
}

$("series").addEventListener("change", async (e) => {
  await saveSettings({ series: e.target.value, episode: "" });
  await loadEpisodes();
});
$("episode").addEventListener("change", (e) => saveSettings({ episode: e.target.value }));
$("new-episode").addEventListener("click", async () => {
  if (!settings.series) return;
  try {
    const ep = await getJson(createEpisodeUrl(settings.series), {
      method: "POST",
      headers: { ...CLIENT_HEADERS, "Content-Type": "application/json" },
      body: "{}",
    });
    await saveSettings({ episode: ep.id });
    await loadEpisodes();
  } catch {
    /* 連線問題會由狀態列顯示 */
  }
});

function renderMode() {
  document.querySelectorAll('input[name="mode"]').forEach((r) => (r.checked = r.value === settings.mode));
  $("mode-hint").hidden = settings.mode !== "save";
}
document.querySelectorAll('input[name="mode"]').forEach((r) =>
  r.addEventListener("change", () => saveSettings({ mode: r.value })),
);

// ── 快捷鍵 ─────────────────────────────────────────────
async function loadShortcut() {
  const commands = await chrome.commands.getAll();
  shortcut = commands.find((c) => c.name === "capture")?.shortcut ?? "";
  const el = $("shortcut");
  if (shortcut) {
    const [before, after] = msg("shortcutHint", ["{KEY}"]).split("{KEY}");
    const kbd = document.createElement("kbd");
    kbd.textContent = shortcut;
    el.replaceChildren(before, kbd, after ?? "");
  } else {
    el.textContent = msg("shortcutUnset");
  }
}
$("change-shortcut").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: "chrome://extensions/shortcuts" });
});
$("capture").addEventListener("click", () => chrome.runtime.sendMessage({ type: "capture" }));

// ── 截圖狀態 ───────────────────────────────────────────
let current = null;

function show(part) {
  for (const id of ["job-empty", "job-working", "job-result", "job-error"]) $(id).hidden = id !== part;
}

function renderJob(job) {
  current = job;
  const small = job?.small;
  $("small-hint").hidden = !small;
  if (small) $("small-hint").textContent = msg("smallCapture", [String(small.width), String(small.height)]);
  if (!job) return show("job-empty");
  const working = { capturing: "stepCapturing", translating: "stepTranslating", saving: "stepSaving" }[job.state];
  // 保險：背景程式萬一被 Chrome 關掉又沒有重新啟動，不要永遠停在「翻譯中」
  if (working && Date.now() - job.id > STALE_MS) {
    job = { ...job, state: "error", error: { key: "errInterrupted", detail: "" } };
    current = job;
  }
  $("capture").disabled = job.state === "capturing";
  if (job.state !== "error" && working) {
    $("job-step").textContent = msg(working);
    return show("job-working");
  }
  if (job.state === "error") {
    const key = job.error?.key ?? "errGeneric";
    $("error-text").textContent = key === "captureNeedsShortcut" ? msg(key, [shortcut || "Alt+Shift+Y"]) : msg(key, [job.error?.detail ?? ""]);
    $("error-detail").textContent = key === "errGeneric" ? "" : job.error?.detail ?? "";
    return show("job-error");
  }

  const saved = job.saved;
  $("open-reader").hidden = !saved;
  if (job.state === "saved") {
    $("result-title").textContent = msg("savedAs", [msg("episodeShort", [episodeNumber(saved.episode)]), String(Number(saved.page))]);
    $("result-image").src = job.original ?? "";
    $("hold").hidden = true;
    $("result-meta").textContent = "";
    $("result-warnings").replaceChildren();
    return show("job-result");
  }

  // done
  const meta = job.meta ?? {};
  $("result-title").textContent = saved
    ? `${msg("resultTitle")} · ${msg("savedAs", [msg("episodeShort", [episodeNumber(saved.episode)]), String(Number(saved.page))])}`
    : msg("resultTitle");
  $("result-image").src = job.result ?? "";
  $("hold").hidden = !job.original;
  const parts = [];
  if (meta.regions === 0) parts.push(msg("noText"));
  if (meta.newTerms) parts.push(msg("newTerms", [String(meta.newTerms)]));
  if (meta.seconds) parts.push(msg("seconds", [String(meta.seconds)]));
  $("result-meta").textContent = parts.join(" · ");
  $("result-warnings").replaceChildren(
    ...(meta.warnings ?? []).map((w) => Object.assign(document.createElement("li"), { textContent: w })),
  );
  show("job-result");
}

// 按住按鈕（或空白鍵）暫時看原文
const showOriginal = (on) => {
  if (!current?.original || current.state !== "done") return;
  $("result-image").src = on ? current.original : current.result;
};
$("hold").addEventListener("pointerdown", () => showOriginal(true));
for (const ev of ["pointerup", "pointerleave", "pointercancel"]) $("hold").addEventListener(ev, () => showOriginal(false));
addEventListener("keydown", (e) => {
  if (e.key === " " && e.target === document.body) {
    e.preventDefault();
    showOriginal(true);
  }
});
addEventListener("keyup", (e) => e.key === " " && showOriginal(false));

$("open-reader").addEventListener("click", () => {
  const s = current?.saved;
  if (s) chrome.tabs.create({ url: readerUrl(s.series, s.episode, s.page) });
});
$("open-app").addEventListener("click", () => chrome.tabs.create({ url: appUrl() }));

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.job) renderJob(changes.job.newValue);
  if (area === "session" && changes.job?.newValue?.state === "saved") loadEpisodes();
});

// ── 啟動 ───────────────────────────────────────────────
await loadSettings();
renderMode();
await loadShortcut();
renderJob((await chrome.storage.session.get("job")).job);
await checkServer();
setInterval(checkServer, 5000);
