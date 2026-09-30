"""啟動器主程式。

第一次啟動（或程式更新後執行環境要重裝）→ 首次啟動精靈；
之後 → 啟動翻譯伺服器、打開 Yomitoki 視窗，系統匣圖示負責叫出視窗與結束。
關閉視窗只會縮到系統匣；從系統匣選「結束」才會關掉翻譯伺服器。
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

from ..bootstrap import is_ready
from .runtime import (SERVER_URL, ServerProcess, SingleInstance, clear_pid, detect_layout, load_state, runtime_python,
                      write_pid)
from .setup_api import SetupApi

log = logging.getLogger("yomitoki.launcher")
WEB = Path(__file__).parent / "web"
APP_ID = "Yomitoki.Reader"


class Launcher:
    def __init__(self):
        self.layout = detect_layout()
        self.server = ServerProcess(self.layout)
        self.window = None
        self.tray = None
        self.quitting = False
        self.instance = SingleInstance(self.layout)

    # ── 啟動 ──
    def run(self) -> int:
        self._setup_logging()
        if not self.instance.acquire():
            # 已經有一個在跑：請它把視窗叫出來
            self.instance.ask_existing_to_show()
            return 0
        write_pid(self.layout, "launcher", os.getpid())
        _set_app_id()

        import webview

        needs_setup = not self._runtime_ok() or not load_state(self.layout).get("setup_done")
        if needs_setup:
            api = SetupApi(self.layout, self.server, on_finish=self._open_main)
            self.window = webview.create_window("Yomitoki", str(WEB / "setup.html"), js_api=api,
                                                width=880, height=680, min_size=(640, 560), background_color="#F7F0E4")
        else:
            self.window = webview.create_window("Yomitoki", str(WEB / "starting.html"), width=1200, height=820,
                                                min_size=(720, 560), background_color="#F7F0E4")
            threading.Thread(target=self._boot_server_then_show_app, daemon=True).start()

        self.window.events.closing += self._on_closing
        self.window.events.shown += self._on_shown
        threading.Thread(target=self._watch_show_requests, daemon=True).start()
        self._start_tray()
        storage = self.layout.root / "webview"
        webview.start(http_server=True, private_mode=False, storage_path=str(storage))
        self._shutdown()
        return 0

    def _runtime_ok(self) -> bool:
        if os.environ.get("YOMITOKI_RUNTIME_PYTHON"):
            return runtime_python(self.layout).is_file()
        return is_ready(self.layout)

    def _boot_server_then_show_app(self) -> None:
        self.server.start()
        if not self.server.error and self.server.wait_ready():
            self.window.load_url(SERVER_URL + "/")
        else:
            msg = (self.server.error or "翻譯伺服器沒有啟動").replace("\\", "\\\\").replace("'", "\\'")
            self.window.evaluate_js(f"window.showError && window.showError('{msg}')")

    def _open_main(self) -> None:
        """精靈完成：同一個視窗換成 Yomitoki 主畫面。"""
        if not self.server.running and not self.server.error:
            self.server.start()
        if self.server.wait_ready(timeout=240):
            self.window.resize(1200, 820)
            self.window.load_url(SERVER_URL + "/")

    # ── 視窗 ──
    def _on_closing(self):
        if self.quitting:
            return True
        # 關視窗只縮到系統匣，翻譯伺服器繼續在背景待命
        self.window.hide()
        return False

    def _on_shown(self):
        _set_window_icon(self.window, self.layout.program / "assets" / "icons" / "app.ico")

    def show(self) -> None:
        if self.window:
            self.window.show()
            self.window.restore()

    def _watch_show_requests(self) -> None:
        while not self.quitting:
            if self.instance.take_show_request():
                self.show()
            time.sleep(1)

    # ── 系統匣 ──
    def _start_tray(self) -> None:
        try:
            import pystray
            from PIL import Image
        except ImportError:
            log.warning("沒有 pystray，略過系統匣圖示")
            return
        icon_path = self.layout.program / "assets" / "icons" / "app-icon-128.png"
        image = Image.open(icon_path) if icon_path.is_file() else Image.new("RGBA", (64, 64), (217, 139, 106, 255))
        zh = _is_zh()
        menu = pystray.Menu(
            pystray.MenuItem("打開 Yomitoki" if zh else "Open Yomitoki", lambda: self.show(), default=True),
            pystray.MenuItem("開啟作品資料夾" if zh else "Open series folder", lambda: self._open_series_folder()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("結束 Yomitoki" if zh else "Quit Yomitoki", lambda: self.quit()),
        )
        self.tray = pystray.Icon("Yomitoki", image, "Yomitoki", menu)
        threading.Thread(target=self.tray.run, name="yomitoki-tray", daemon=True).start()

    def _open_series_folder(self) -> None:
        from .. import paths

        folder = paths.data_home() / "series"
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # noqa: S606

    def quit(self) -> None:
        self.quitting = True
        if self.window:
            self.window.destroy()

    def _shutdown(self) -> None:
        self.quitting = True
        self.server.stop()
        if self.tray:
            self.tray.stop()
        clear_pid(self.layout, "launcher")

    def _setup_logging(self) -> None:
        self.layout.logs.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=self.layout.logs / "launcher.log", level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s %(name)s %(levelname)s %(message)s")


def _is_zh() -> bool:
    from .setup_api import _system_locale

    return _system_locale() == "zh-TW"


def _set_app_id() -> None:
    """讓工作列用 Yomitoki 自己的圖示，而不是 Python 的。"""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (OSError, AttributeError):
            pass


def _set_window_icon(window, ico: Path) -> None:
    if sys.platform != "win32" or not ico.is_file():
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, window.title)
        if not hwnd:
            return
        LR_LOADFROMFILE, IMAGE_ICON, WM_SETICON = 0x10, 1, 0x80
        for size, which in ((16, 0), (32, 1)):
            h = user32.LoadImageW(None, str(ico), IMAGE_ICON, size, size, LR_LOADFROMFILE)
            if h:
                user32.SendMessageW(hwnd, WM_SETICON, which, h)
    except (OSError, AttributeError):
        pass


def main() -> int:
    try:
        return Launcher().run()
    except Exception:  # noqa: BLE001 — 沒有主控台，錯誤一定要寫進記錄檔
        log.exception("啟動器發生錯誤")
        raise
