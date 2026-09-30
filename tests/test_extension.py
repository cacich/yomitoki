"""瀏覽器插件的靜態檢查：權限、使用界線、語系檔、與 ui/ 同步的檔案。"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "extension"
MANIFEST = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
LOCALES = {p.parent.name: json.loads(p.read_text(encoding="utf-8")) for p in EXT.glob("_locales/*/messages.json")}
SOURCES = {p.name: p.read_text(encoding="utf-8") for p in EXT.glob("*") if p.suffix in (".js", ".html") and ".test." not in p.name}


def test_manifest_v3_with_minimal_permissions():
    assert MANIFEST["manifest_version"] == 3
    # 只在使用者按快捷鍵或點圖示時取得截圖權限（activeTab），不要求讀取所有網站
    assert sorted(MANIFEST["permissions"]) == ["activeTab", "sidePanel", "storage"]
    assert MANIFEST["host_permissions"] == ["http://127.0.0.1:8765/*"]
    assert "content_scripts" not in MANIFEST
    assert MANIFEST["commands"]["capture"]["suggested_key"]["default"] == "Alt+Shift+Y"
    assert MANIFEST["background"]["type"] == "module"


def test_icons_exist():
    paths = set(MANIFEST["icons"].values()) | set(MANIFEST["action"]["default_icon"].values())
    for rel in paths:
        assert (EXT / rel).is_file(), rel


def test_respects_usage_boundaries():
    """只擷取可見畫面：不下載、不攔截、不讀取網頁裡的圖片，也不自動操作頁面。"""
    code = "\n".join(SOURCES.values())
    forbidden = ["webRequest", "chrome.downloads", "chrome.scripting", "executeScript", "chrome.debugger",
                 "<all_urls>", "document.images", "querySelectorAll('img')", "scrollBy", "scrollTo"]
    for token in forbidden:
        assert token not in code, token
    assert "captureVisibleTab" in SOURCES["background.js"]
    # 只連到本機的 Yomitoki
    hosts = set(re.findall(r"https?://([\w.\-]+(?::\d+)?)", code))
    assert hosts <= {"127.0.0.1:8765"}, hosts


def test_background_stays_alive_during_long_requests():
    """翻譯一頁常超過 30 秒；Chrome 會在 30 秒沒有事件時關掉 service worker、中斷 fetch。"""
    bg = SOURCES["background.js"]
    assert "getPlatformInfo" in bg and "keepAlive()" in bg
    assert "AbortSignal.timeout" in bg
    assert '"errInterrupted"' in bg  # 重新啟動時把卡住的工作標成中斷


def test_locales_match():
    assert set(LOCALES) == {"zh_TW", "en"}
    zh, en = LOCALES["zh_TW"], LOCALES["en"]
    assert set(zh) == set(en)
    for key in zh:
        assert set(zh[key].get("placeholders", {})) == set(en[key].get("placeholders", {})), key
    assert MANIFEST["default_locale"] == "zh_TW"


def test_every_message_key_exists():
    keys = set(LOCALES["zh_TW"])
    manifest_text = json.dumps(MANIFEST)
    used = set(re.findall(r"__MSG_(\w+)__", manifest_text))
    for name, text in SOURCES.items():
        used |= set(re.findall(r'data-i18n="(\w+)"', text))
        used |= set(re.findall(r'\bmsg\("(\w+)"', text))
    # 由 background.js 設定、在面板裡顯示的錯誤代碼
    used |= set(re.findall(r'"(err[A-Z]\w+|captureNeedsShortcut|modeSaveNeedsSeries)"', "\n".join(SOURCES.values())))
    used |= set(re.findall(r'key: "(\w+)"', (EXT / "lib.js").read_text(encoding="utf-8")))
    assert used - keys == set(), used - keys
    assert len(used) > 30


def test_copied_files_are_in_sync():
    assert (EXT / "tokens.css").read_bytes() == (ROOT / "ui" / "src" / "styles" / "tokens.css").read_bytes(), \
        "tokens.css 不同步：請執行 python scripts/sync-shared.py"
    for s in (16, 32, 48, 128):
        src = ROOT / "assets" / "icons" / "extension" / f"icon-{s}.png"
        assert (EXT / "icons" / f"icon-{s}.png").read_bytes() == src.read_bytes(), f"icon-{s}.png 不同步"
