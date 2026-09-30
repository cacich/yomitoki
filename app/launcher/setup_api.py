"""首次啟動精靈的 Python 端：頁面透過 window.pywebview.api.<方法>() 呼叫這些方法。

每個方法都回傳可以轉成 JSON 的資料；錯誤不丟例外，而是回傳 {"ok": False, "error": "..."}，
讓頁面可以直接顯示。
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from .. import __version__
from ..assets import AssetRegistry
from ..bootstrap import NO_WINDOW, Layout, RuntimeInstaller, environment_check, is_ready
from ..languages import SOURCES, TARGETS
from .runtime import SERVER_URL, ServerProcess, runtime_python, save_state

log = logging.getLogger("yomitoki.launcher.setup")

CLAUDE_DOCS = "https://docs.claude.com/en/docs/claude-code/overview"
CREATE_NEW_CONSOLE = 0x00000010
CLIENT_HEADERS = {"X-Yomitoki-Client": "launcher"}


class SetupApi:
    def __init__(self, layout: Layout, server: ServerProcess, on_finish=None):
        self._layout = layout
        self._server = server
        self._on_finish = on_finish
        self._installer: RuntimeInstaller | None = None
        self._assets = AssetRegistry(builtin_dir=layout.program / "assets")
        self._server_thread: threading.Thread | None = None
        self._server_state = {"status": "stopped", "error": None}

    # ── 基本資訊與素材 ──
    def info(self) -> dict:
        return {
            "version": __version__,
            "root": str(self._layout.root),
            "extension_dir": str(self._layout.program / "extension"),
            "runtime_ready": self._runtime_ready(),
            "locale": _system_locale(),
        }

    def asset(self, asset_id: str) -> str:
        """頁面沒辦法讀本機檔案，素材一律轉成 data URL（也會套用使用者自訂的圖片）。"""
        try:
            return _data_url(self._assets.resolve(asset_id))
        except Exception:  # noqa: BLE001
            return ""

    def languages(self) -> dict:
        return {
            "sources": [{"code": k, "name": v.name} for k, v in SOURCES.items() if v.status == "supported"],
            "targets": [{"code": k, "name": v.name} for k, v in TARGETS.items() if v.status == "supported"],
        }

    # ── 1. 環境檢查 ──
    def check_environment(self) -> dict:
        return environment_check(self._layout)

    # ── 2. 下載元件 ──
    def start_install(self, device: str) -> dict:
        if self._runtime_ready():
            return {"ok": True, "already": True}
        try:
            self._installer = RuntimeInstaller(self._layout, device)
        except ValueError:
            return {"ok": False, "error": f"不支援的裝置：{device}"}
        self._installer.start()
        return {"ok": True}

    def install_progress(self) -> dict:
        if self._runtime_ready() and (self._installer is None or self._installer.progress.status == "done"):
            return {"status": "done", "fraction": 1.0, "step": None, "detail": "", "downloaded_mb": 0, "error": None, "log": []}
        if self._installer is None:
            return {"status": "idle", "fraction": 0.0, "step": None, "detail": "", "downloaded_mb": 0, "error": None, "log": []}
        return self._installer.progress.to_dict()

    def open_logs(self) -> None:
        self._layout.logs.mkdir(parents=True, exist_ok=True)
        _open_folder(self._layout.logs)

    # ── 啟動翻譯伺服器（下載完成後） ──
    def start_server(self) -> dict:
        if self._server_thread and self._server_thread.is_alive():
            return {"ok": True}

        def run():
            self._server_state = {"status": "starting", "error": None}
            self._server.start()
            if self._server.error:
                self._server_state = {"status": "error", "error": self._server.error}
            elif self._server.wait_ready():
                self._server_state = {"status": "ready", "error": None}
            else:
                self._server_state = {"status": "error", "error": self._server.error}

        self._server_thread = threading.Thread(target=run, daemon=True)
        self._server_thread.start()
        return {"ok": True}

    def server_status(self) -> dict:
        return dict(self._server_state)

    # ── 3. Claude Code ──
    def claude_status(self) -> dict:
        exe = shutil.which("claude")
        status = {"installed": bool(exe), "logged_in": False, "subscription": None, "version": None}
        if not exe:
            return status
        try:
            v = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", timeout=20,
                               creationflags=NO_WINDOW)
            status["version"] = (v.stdout.strip().split(" ") or [None])[0]
            s = subprocess.run([exe, "auth", "status", "--json"], capture_output=True, text=True, encoding="utf-8",
                               timeout=20, creationflags=NO_WINDOW)
            data = json.loads(s.stdout or "{}")
            # 只取登入狀態與方案，不讀帳號 email
            status["logged_in"] = bool(data.get("loggedIn"))
            status["subscription"] = data.get("subscriptionType")
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return status

    def open_claude_login(self) -> dict:
        """開一個終端機視窗執行 claude，讓使用者自己完成登入。"""
        exe = shutil.which("claude")
        if not exe:
            return {"ok": False, "error": "找不到 claude 指令"}
        subprocess.Popen(["cmd.exe", "/k", exe], creationflags=CREATE_NEW_CONSOLE)
        return {"ok": True}

    def open_claude_docs(self) -> None:
        webbrowser.open(CLAUDE_DOCS)

    # ── 4. 瀏覽器插件 ──
    def open_extensions_page(self) -> dict:
        chrome = _find_chrome()
        if not chrome:
            return {"ok": False, "error": "找不到 Chrome"}
        subprocess.Popen([chrome, "chrome://extensions"])
        return {"ok": True}

    def open_extension_folder(self) -> None:
        _open_folder(self._layout.program / "extension")

    # ── 5. 第一部作品 ──
    def create_series(self, name: str, fmt: str, source: str, target: str) -> dict:
        body = json.dumps({"name": name, "format": fmt, "source_lang": source, "target_lang": target}).encode()
        return _request("POST", "/api/series", body, {"Content-Type": "application/json"})

    # ── 6. 試翻一張 ──
    def trial_translate(self) -> dict:
        sample = self._layout.program / "assets" / "samples" / "ja-page-01.png"
        data = sample.read_bytes()
        started = time.monotonic()
        req = urllib.request.Request(f"{SERVER_URL}/translate", data=data, method="POST",
                                     headers={**CLIENT_HEADERS, "Content-Type": "image/png"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                out = r.read()
                regions = int(r.headers.get("X-Yomitoki-Regions", "0"))
        except urllib.error.HTTPError as e:
            return {"ok": False, "status": e.code, "error": _detail(e)}
        except (urllib.error.URLError, OSError) as e:
            return {"ok": False, "status": 0, "error": str(e)}
        return {"ok": True, "regions": regions, "seconds": round(time.monotonic() - started, 1),
                "original": _data_url_bytes(data, "image/png"), "result": _data_url_bytes(out, "image/png")}

    # ── 完成 ──
    def finish(self) -> None:
        save_state(self._layout, setup_done=True, finished=time.strftime("%Y-%m-%d %H:%M:%S"))
        if self._on_finish:
            threading.Thread(target=self._on_finish, daemon=True).start()

    def _runtime_ready(self) -> bool:
        if os.environ.get("YOMITOKI_RUNTIME_PYTHON"):
            return runtime_python(self._layout).is_file()
        return is_ready(self._layout)


# ── 工具 ─────────────────────────────────────────────────────

def _data_url(path: Path) -> str:
    mime = "image/svg+xml" if path.suffix == ".svg" else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return _data_url_bytes(path.read_bytes(), mime)


def _data_url_bytes(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _request(method: str, path: str, body: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(f"{SERVER_URL}{path}", data=body, method=method, headers={**CLIENT_HEADERS, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"ok": True, "data": json.loads(r.read().decode("utf-8") or "null")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": _detail(e)}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "status": 0, "error": str(e)}


def _detail(e: urllib.error.HTTPError) -> str:
    try:
        return json.loads(e.read().decode("utf-8")).get("detail") or str(e)
    except (ValueError, OSError):
        return str(e)


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — 只開啟本機資料夾
    else:
        webbrowser.open(path.as_uri())


def _find_chrome() -> str | None:
    """先查 Windows 的 App Paths 登錄，再找常見安裝位置。"""
    if sys.platform == "win32":
        import winreg

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as k:
                    path = winreg.QueryValue(k, None)
                    if path and Path(path).is_file():
                        return path
            except OSError:
                pass
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                p = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
                if p.is_file():
                    return str(p)
    return shutil.which("chrome") or shutil.which("google-chrome")


def _system_locale() -> str:
    try:
        import locale

        lang = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):
        lang = ""
    if sys.platform == "win32":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(85)
            ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
            lang = buf.value.lower() or lang
        except (OSError, AttributeError):
            pass
    return "zh-TW" if lang.startswith("zh") or "chinese" in lang else "en"
