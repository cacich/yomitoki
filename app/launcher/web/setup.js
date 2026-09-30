// 首次啟動精靈。Python 端的方法見 app/launcher/setup_api.py（window.pywebview.api.*）。
"use strict";

const MESSAGES = {
  "zh-TW": {
    common: { next: "下一步", back: "上一步", skip: "先跳過", retry: "重試" },
    welcome: {
      eyebrow: "歡迎", title: "一起把看不懂的漫畫讀懂吧",
      lead: "接下來由我帶你完成幾個步驟。大部分時間是在下載，你可以先去泡杯茶。",
      item1: "檢查這台電腦的顯示卡與磁碟空間", item2: "下載翻譯需要的元件與模型（約 3～5 GB）",
      item3: "連接 Claude Code、安裝瀏覽器插件，然後試翻一張",
      notice: "Yomitoki 只供個人閱讀理解。請遵守各平台條款與著作權法，翻譯結果不要分享或上傳。",
      start: "開始",
    },
    env: {
      title: "先看看你的電腦", gpu: "顯示卡", disk: "磁碟空間",
      gpuOk: "{name}（{vram} GB），會用它加速", gpuNone: "沒有偵測到 NVIDIA 顯示卡",
      cpuNote: "沒有 NVIDIA 顯示卡也可以用，會改用 CPU 模式，每頁會慢上好幾倍。",
      diskOk: "可用 {free} GB（需要約 {need} GB）", diskLow: "只剩 {free} GB，至少需要 {need} GB。請先清出空間再繼續。",
    },
    download: {
      title: "下載元件", lead: "會下載 Python 環境、翻譯核心與模型。依網路速度大約需要 10～30 分鐘。",
      start: "開始下載", logs: "查看記錄", failed: "下載沒有完成",
      step_python: "準備 Python", step_venv: "建立執行環境", step_packages: "安裝翻譯核心的套件",
      step_torch: "安裝 PyTorch（最大的一個，約 {size}）", step_engine: "下載 manga-image-translator",
      step_models: "下載文字偵測、OCR 與擦字模型", step_finish: "收尾", downloaded: "已下載 {mb} MB",
      server: "啟動翻譯引擎中…（第一次約 20～40 秒）", serverFailed: "翻譯引擎沒有啟動：{error}",
      done: "元件都準備好了。",
    },
    claude: {
      title: "連接 Claude Code", lead: "翻譯交給你自己登入的 Claude Code，不需要 API key，額度與你的 Claude 訂閱共用。截圖不會離開你的電腦，只會送出辨識出的文字。",
      checking: "檢查中…", missing: "還沒安裝 Claude Code", missingHint: "照官方說明安裝後，按「重新檢查」。",
      loggedOut: "已安裝，但還沒登入", loggedOutHint: "按「開啟終端機登入」，在跳出的視窗裡依照指示登入，完成後按「重新檢查」。",
      ok: "已登入（{plan}）", okHint: "版本 {version}",
      install: "打開安裝說明", login: "開啟終端機登入", recheck: "重新檢查",
    },
    extension: {
      title: "安裝瀏覽器插件", lead: "在 Chrome 看漫畫時按 Alt+Shift+Y，就能把畫面交給 Yomitoki 翻譯。",
      step1: "打開 Chrome 的擴充功能頁", openPage: "打開擴充功能頁",
      step2: "打開右上角的「開發人員模式」", step3: "按「載入未封裝項目」，選這個資料夾：",
      copy: "複製路徑", copied: "已複製", openFolder: "開啟資料夾",
      step4: "點工具列的拼圖圖示，把 Yomitoki 釘選起來", done: "裝好了", noChrome: "找不到 Chrome，請手動在網址列輸入 chrome://extensions",
    },
    series: {
      title: "建立第一部作品", lead: "每部作品有自己的詞彙表與劇情摘要，讓角色名每一頁都翻得一樣。之後也可以在書架新增。",
      name: "作品名", format: "格式", formatPage: "頁漫（一頁一頁翻）", source: "原文", target: "翻成", create: "建立",
    },
    trial: {
      title: "試翻一張", lead: "用內建的原創範例圖跑一次完整流程，確認一切正常。",
      run: "試翻", running: "辨識、翻譯、嵌字中…（約 20～60 秒）", original: "原圖", result: "譯圖",
      ok: "成功了！花了 {s} 秒，翻了 {n} 個對話框。", finish: "開始使用 Yomitoki",
      needLogin: "Claude Code 還沒登入，所以沒辦法翻譯。可以先跳過，登入後再到書架試。",
    },
  },
  en: {
    common: { next: "Next", back: "Back", skip: "Skip for now", retry: "Retry" },
    welcome: {
      eyebrow: "Welcome", title: "Let's make that manga readable",
      lead: "I'll walk you through a few steps. Most of the time is downloading, so feel free to grab a tea.",
      item1: "Check this computer's graphics card and disk space", item2: "Download the translation components and models (about 3–5 GB)",
      item3: "Connect Claude Code, install the browser extension, then try one page",
      notice: "Yomitoki is for personal reading only. Follow each site's terms and copyright law, and don't share translated pages.",
      start: "Start",
    },
    env: {
      title: "A quick look at your computer", gpu: "Graphics card", disk: "Disk space",
      gpuOk: "{name} ({vram} GB), used for acceleration", gpuNone: "No NVIDIA graphics card found",
      cpuNote: "Yomitoki still works without an NVIDIA card. It runs on the CPU instead, several times slower per page.",
      diskOk: "{free} GB free (about {need} GB needed)", diskLow: "Only {free} GB free; at least {need} GB is needed. Free up some space first.",
    },
    download: {
      title: "Download components", lead: "This downloads Python, the translation engine and the models. It takes about 10–30 minutes depending on your connection.",
      start: "Start download", logs: "View log", failed: "The download didn't finish",
      step_python: "Preparing Python", step_venv: "Creating the environment", step_packages: "Installing the engine's packages",
      step_torch: "Installing PyTorch (the big one, about {size})", step_engine: "Downloading manga-image-translator",
      step_models: "Downloading the detection, OCR and inpainting models", step_finish: "Finishing up", downloaded: "{mb} MB downloaded",
      server: "Starting the translation engine… (20–40 s the first time)", serverFailed: "The translation engine didn't start: {error}",
      done: "Everything is ready.",
    },
    claude: {
      title: "Connect Claude Code", lead: "Translation runs through your own signed-in Claude Code. No API key is needed; it uses your Claude subscription. Screenshots never leave your computer, only the recognized text.",
      checking: "Checking…", missing: "Claude Code isn't installed", missingHint: "Install it following the official guide, then press “Check again”.",
      loggedOut: "Installed, but not signed in", loggedOutHint: "Press “Sign in in a terminal”, follow the steps in the new window, then press “Check again”.",
      ok: "Signed in ({plan})", okHint: "Version {version}",
      install: "Open install guide", login: "Sign in in a terminal", recheck: "Check again",
    },
    extension: {
      title: "Install the browser extension", lead: "While reading manga in Chrome, press Alt+Shift+Y to send the page to Yomitoki.",
      step1: "Open Chrome's extensions page", openPage: "Open extensions page",
      step2: "Turn on “Developer mode” in the top right", step3: "Click “Load unpacked” and choose this folder:",
      copy: "Copy path", copied: "Copied", openFolder: "Open folder",
      step4: "Click the puzzle icon in the toolbar and pin Yomitoki", done: "Done", noChrome: "Chrome wasn't found. Type chrome://extensions in the address bar yourself.",
    },
    series: {
      title: "Add your first series", lead: "Each series keeps its own glossary and story notes, so names stay consistent. You can add more from the shelf later.",
      name: "Series name", format: "Format", formatPage: "Pages (turn page by page)", source: "From", target: "Into", create: "Create",
    },
    trial: {
      title: "Try one page", lead: "Run the built-in original sample through the whole pipeline to make sure everything works.",
      run: "Try it", running: "Reading, translating and typesetting… (about 20–60 s)", original: "Original", result: "Translated",
      ok: "It works! {n} bubbles translated in {s} s.", finish: "Start using Yomitoki",
      needLogin: "Claude Code isn't signed in, so translation can't run yet. Skip for now and try from the shelf after signing in.",
    },
  },
};

const STEPS = ["welcome", "env", "download", "claude", "extension", "series", "trial"];
const MASCOTS = { welcome: "mascot-welcome", download: "mascot-loading", trial: "mascot-guide" };
const $ = (id) => document.getElementById(id);
let locale = "zh-TW";
let api = null;
let env = null;
const images = {};

function t(key, vars) {
  const parts = key.split(".");
  let node = MESSAGES[locale];
  for (const p of parts) node = node?.[p];
  if (typeof node !== "string") {
    node = parts.reduce((n, p) => n?.[p], MESSAGES["zh-TW"]);
  }
  return String(node ?? key).replace(/\{(\w+)\}/g, (m, k) => (vars && k in vars ? vars[k] : m));
}

function applyText() {
  document.documentElement.lang = locale === "zh-TW" ? "zh-Hant" : "en";
  document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
}

async function mascot(step) {
  const id = MASCOTS[step] ?? "mascot-guide";
  if (!images[id]) images[id] = await api.asset(id);
  $("mascot").src = images[id];
}

function go(step) {
  document.querySelectorAll(".step").forEach((el) => (el.hidden = el.dataset.step !== step));
  const i = STEPS.indexOf(step);
  $("dots").querySelectorAll("li").forEach((li, j) => (li.className = j < i ? "done" : j === i ? "now" : ""));
  mascot(step);
  ({ env: loadEnv, download: prepareDownload, claude: checkClaude, extension: loadExtension, series: loadSeries })[step]?.();
}

// ── 1. 環境檢查 ──
async function loadEnv() {
  env = await api.check_environment();
  const g = env.gpu;
  $("env-gpu-dot").className = "dot " + (g.nvidia ? "ok" : "warn");
  $("env-gpu").textContent = g.nvidia ? t("env.gpuOk", { name: g.name, vram: g.vram_gb }) : t("env.gpuNone");
  $("env-cpu-note").hidden = g.nvidia;
  $("env-disk-dot").className = "dot " + (env.disk_ok ? "ok" : "bad");
  $("env-disk").textContent = t(env.disk_ok ? "env.diskOk" : "env.diskLow", { free: env.free_gb, need: env.required_gb });
  $("env-next").disabled = !env.disk_ok;
}

// ── 2. 下載元件 ──
let polling = null;
async function prepareDownload() {
  const info = await api.info();
  if (info.runtime_ready) return afterDownload();
  $("download-start").hidden = false;
}

async function startDownload() {
  $("download-start").hidden = true;
  $("download-error").hidden = true;
  const res = await api.start_install(env?.device ?? "cpu");
  if (!res.ok) return showDownloadError(res.error);
  if (res.already) return afterDownload();
  polling = setInterval(pollDownload, 1000);
}

async function pollDownload() {
  const p = await api.install_progress();
  const pct = Math.round((p.fraction ?? 0) * 100);
  $("download-fill").style.width = pct + "%";
  $("download-bar").setAttribute("aria-valuenow", String(pct));
  if (p.step) {
    const size = env?.device === "cuda" ? "2.7 GB" : "260 MB";
    let label = t(`download.step_${p.step}`, { size });
    if (p.downloaded_mb && (p.step === "torch" || p.step === "packages")) label += " · " + t("download.downloaded", { mb: p.downloaded_mb });
    $("download-step").textContent = `${pct}% · ${label}`;
  }
  $("download-detail").textContent = p.detail ?? "";
  if (p.status === "error") {
    clearInterval(polling);
    showDownloadError(p.error);
  } else if (p.status === "done") {
    clearInterval(polling);
    afterDownload();
  }
}

function showDownloadError(message) {
  $("download-error").hidden = false;
  $("download-error-text").textContent = message ?? "";
  $("download-start").hidden = false;
  $("download-start").textContent = t("common.retry");
}

async function afterDownload() {
  $("download-fill").style.width = "100%";
  $("download-start").hidden = true;
  $("download-step").textContent = t("download.server");
  $("download-detail").textContent = "";
  await api.start_server();
  const timer = setInterval(async () => {
    const s = await api.server_status();
    if (s.status === "ready") {
      clearInterval(timer);
      $("download-step").textContent = t("download.done");
      setTimeout(() => go("claude"), 600);
    } else if (s.status === "error") {
      clearInterval(timer);
      showDownloadError(t("download.serverFailed", { error: s.error }));
    }
  }, 1000);
}

// ── 3. Claude Code ──
let claudeOk = false;
async function checkClaude() {
  $("claude-dot").className = "dot wait";
  $("claude-status").textContent = t("claude.checking");
  $("claude-hint").textContent = "";
  $("claude-actions").replaceChildren();
  const s = await api.claude_status();
  claudeOk = s.installed && s.logged_in;
  const btn = (label, fn, primary) => {
    const b = document.createElement("button");
    b.className = "btn btn--small" + (primary ? " btn--primary" : "");
    b.textContent = label;
    b.onclick = fn;
    return b;
  };
  const recheck = btn(t("claude.recheck"), checkClaude);
  if (!s.installed) {
    $("claude-dot").className = "dot bad";
    $("claude-status").textContent = t("claude.missing");
    $("claude-hint").textContent = t("claude.missingHint");
    $("claude-actions").append(btn(t("claude.install"), () => api.open_claude_docs(), true), recheck);
  } else if (!s.logged_in) {
    $("claude-dot").className = "dot warn";
    $("claude-status").textContent = t("claude.loggedOut");
    $("claude-hint").textContent = t("claude.loggedOutHint");
    $("claude-actions").append(btn(t("claude.login"), () => api.open_claude_login(), true), recheck);
  } else {
    $("claude-dot").className = "dot ok";
    $("claude-status").textContent = t("claude.ok", { plan: s.subscription ?? "" });
    $("claude-hint").textContent = t("claude.okHint", { version: s.version ?? "" });
  }
  $("claude-next").disabled = !claudeOk;
}

// ── 4. 瀏覽器插件 ──
async function loadExtension() {
  const info = await api.info();
  $("ext-path").textContent = info.extension_dir;
}

// ── 5. 第一部作品 ──
async function loadSeries() {
  const langs = await api.languages();
  const fill = (el, list, value) => {
    el.replaceChildren(...list.map((l) => new Option(l.name, l.code)));
    el.value = value;
  };
  fill($("series-source"), langs.sources, "ja");
  fill($("series-target"), langs.targets, "zh-TW");
  $("series-name").focus();
}

async function createSeries(e) {
  e.preventDefault();
  const name = $("series-name").value.trim();
  if (!name) return;
  $("series-error").textContent = "";
  const res = await api.create_series(name, $("series-format").value, $("series-source").value, $("series-target").value);
  if (!res.ok) {
    $("series-error").textContent = res.error;
    return;
  }
  go("trial");
}

// ── 6. 試翻一張 ──
async function runTrial() {
  $("trial-run").disabled = true;
  $("trial-error").textContent = "";
  $("trial-status").textContent = t("trial.running");
  $("mascot").src = images["mascot-loading"] ?? (images["mascot-loading"] = await api.asset("mascot-loading"));
  const res = await api.trial_translate();
  $("trial-run").disabled = false;
  mascot("trial");
  if (!res.ok) {
    $("trial-status").textContent = "";
    $("trial-error").textContent = res.status === 401 ? t("trial.needLogin") : res.error;
    return;
  }
  $("trial-compare").hidden = false;
  $("trial-original").src = res.original;
  $("trial-result").src = res.result;
  $("trial-status").textContent = t("trial.ok", { s: res.seconds, n: res.regions });
  $("trial-run").hidden = true;
  $("trial-skip").hidden = true;
  $("trial-finish").hidden = false;
  $("mascot").src = images["mascot-welcome"] ?? (await api.asset("mascot-welcome"));
}

async function init() {
  api = window.pywebview.api;
  const info = await api.info();
  locale = info.locale in MESSAGES ? info.locale : "zh-TW";
  applyText();
  $("dots").replaceChildren(...STEPS.map(() => document.createElement("li")));
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(b.dataset.go)));
  $("env-next").onclick = () => go("download");
  $("download-start").onclick = startDownload;
  $("download-logs").onclick = () => api.open_logs();
  $("claude-next").onclick = () => go("extension");
  $("claude-skip").onclick = () => go("extension");
  $("ext-open").onclick = async () => {
    const r = await api.open_extensions_page();
    $("ext-msg").textContent = r.ok ? "" : t("extension.noChrome");
  };
  $("ext-folder").onclick = () => api.open_extension_folder();
  $("ext-copy").onclick = async () => {
    await navigator.clipboard.writeText($("ext-path").textContent);
    $("ext-copy").textContent = t("extension.copied");
  };
  $("series-form").addEventListener("submit", createSeries);
  $("trial-run").onclick = runTrial;
  $("trial-skip").onclick = () => api.finish();
  $("trial-finish").onclick = () => api.finish();
  go("welcome");
}

if (window.pywebview?.api) init();
else window.addEventListener("pywebviewready", init);
