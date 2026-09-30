// 執行：node --test extension/lib.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  blobToDataUrl,
  dataUrlToBlob,
  describeError,
  episodeNumber,
  isCapturable,
  parseHeaderJson,
  pickEpisode,
  readerUrl,
  translateMeta,
  translateUrl,
  uploadUrl,
} from "./lib.js";

test("translateUrl 只在有作品時帶參數，話數必須搭配作品", () => {
  assert.equal(translateUrl(), "http://127.0.0.1:8765/translate");
  assert.equal(translateUrl({ series: "", episode: "ep001" }), "http://127.0.0.1:8765/translate");
  const url = new URL(translateUrl({ series: "狸貓日記", episode: "ep002" }));
  assert.equal(url.searchParams.get("series"), "狸貓日記");
  assert.equal(url.searchParams.get("episode"), "ep002");
});

test("作品名會被編碼，不會跳出路徑", () => {
  assert.equal(uploadUrl("a/b", "ep001"), "http://127.0.0.1:8765/api/series/a%2Fb/episodes/ep001/pages");
  assert.equal(readerUrl("狸貓", "ep001", "003"), "http://127.0.0.1:8765/read/%E7%8B%B8%E8%B2%93/ep001/003");
});

test("解析回應標頭裡的 JSON", () => {
  const warnings = encodeURIComponent(JSON.stringify(["001#2 沒有譯文"]));
  const seconds = encodeURIComponent(JSON.stringify({ ocr: 4.21, translate: 10.04, render: 0.3 }));
  const meta = translateMeta(new Map([
    ["x-yomitoki-regions", "7"], ["x-yomitoki-new-terms", "1"],
    ["x-yomitoki-warnings", warnings], ["x-yomitoki-seconds", seconds],
  ]));
  assert.deepEqual(meta, { regions: 7, newTerms: 1, warnings: ["001#2 沒有譯文"], seconds: 14.6 });
  assert.deepEqual(parseHeaderJson("%E0%A4%A", []), []);
  assert.deepEqual(parseHeaderJson(null, {}), {});
});

test("錯誤代碼對應到提示訊息", () => {
  assert.equal(describeError(0).key, "errServerDown");
  assert.equal(describeError(401, "x").key, "errClaudeLogin");
  assert.equal(describeError(503).key, "errClaudeMissing");
  assert.deepEqual(describeError(502, "Claude Code 回報錯誤"), { key: "errGeneric", detail: "Claude Code 回報錯誤" });
  assert.equal(describeError(500).detail, "HTTP 500");
});

test("話數與預設選擇", () => {
  assert.equal(episodeNumber("ep012"), "12");
  assert.equal(episodeNumber("ep12.5"), "12.5");
  const eps = [{ id: "ep001" }, { id: "ep002" }];
  assert.equal(pickEpisode(eps, "ep001"), "ep001");
  assert.equal(pickEpisode(eps, "ep009"), "ep002");
  assert.equal(pickEpisode([], "ep001"), null);
});

test("Chrome 不允許擷取的頁面", () => {
  assert.ok(isCapturable("https://example.com/viewer"));
  for (const url of ["chrome://extensions", "chrome-extension://abc/sidepanel.html", "about:blank",
    "https://chromewebstore.google.com/detail/x", ""]) {
    assert.ok(!isCapturable(url), url);
  }
});

test("data URL 與 Blob 互轉", async () => {
  const blob = dataUrlToBlob("data:image/png;base64,iVBORw0KGgo=");
  assert.equal(blob.type, "image/png");
  assert.equal(blob.size, 8);
  assert.equal(await blobToDataUrl(blob), "data:image/png;base64,iVBORw0KGgo=");
});
