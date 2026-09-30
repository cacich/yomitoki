"""啟動器的後端管理：找出安裝位置、啟動與結束翻譯伺服器、只允許一個啟動器同時執行。"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import paths
from ..bootstrap import NO_WINDOW, Layout, runtime_server_command

log = logging.getLogger("yomitoki.launcher")

# 瀏覽器插件固定連 8765；YOMITOKI_PORT 只給測試用（例如已經有另一個伺服器在跑時）
PORT = int(os.environ.get("YOMITOKI_PORT", "8765"))
SERVER_URL = f"http://127.0.0.1:{PORT}"
STATE_FILE = "launcher.json"


def detect_layout() -> Layout:
    """安裝版：程式在 <安裝位置>\\program；開發版：直接從 repo 執行。"""
    program = paths.REPO_ROOT
    if program.name == "program" and (program.parent / "bin").is_dir():
        root = program.parent
    else:
        root = paths.app_home()
    os.environ["YOMITOKI_APP_HOME"] = str(root)  # 讓子程序（翻譯伺服器）用同一個位置
    return Layout(root, program)


def runtime_python(layout: Layout) -> Path:
    """開發時可以用 YOMITOKI_RUNTIME_PYTHON 指到現成的開發環境，略過精靈的下載步驟。"""
    override = os.environ.get("YOMITOKI_RUNTIME_PYTHON")
    return Path(override) if override else layout.runtime_python


# ── 啟動器狀態（精靈是否走完） ────────────────────────────

def load_state(layout: Layout) -> dict:
    try:
        return json.loads((layout.root / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(layout: Layout, **changes) -> dict:
    state = {**load_state(layout), **changes}
    layout.root.mkdir(parents=True, exist_ok=True)
    (layout.root / STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


# ── PID 檔：解除安裝時用來結束還在執行的 Yomitoki ─────────

def pid_dir(layout: Layout) -> Path:
    d = layout.root / "run"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_pid(layout: Layout, name: str, pid: int) -> None:
    (pid_dir(layout) / f"{name}.pid").write_text(str(pid), encoding="ascii")


def clear_pid(layout: Layout, name: str) -> None:
    (pid_dir(layout) / f"{name}.pid").unlink(missing_ok=True)


# ── 翻譯伺服器 ───────────────────────────────────────────

def health(timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/health", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


class ServerProcess:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.proc: subprocess.Popen | None = None
        self.error: str | None = None
        self._log_file = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> None:
        """啟動翻譯伺服器；已經有一個在跑（例如自己在終端機開的）就沿用。"""
        self.error = None
        if health():
            log.info("沿用已經在執行的 Yomitoki 伺服器")
            return
        if self.running:
            return
        python = runtime_python(self.layout)
        if not python.is_file():
            self.error = f"找不到執行環境：{python}"
            return
        cmd = [str(python), *runtime_server_command(self.layout, PORT)[1:]]
        self.layout.logs.mkdir(parents=True, exist_ok=True)
        self._log_file = (self.layout.logs / "server.log").open("a", encoding="utf-8")
        self._log_file.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} 啟動 ====\n")
        self._log_file.flush()
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        self.proc = subprocess.Popen(cmd, cwd=str(self.layout.program), env=env, stdout=self._log_file,
                                     stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        write_pid(self.layout, "server", self.proc.pid)
        log.info("啟動翻譯伺服器 pid=%s", self.proc.pid)

    def wait_ready(self, timeout: float = 240) -> bool:
        """模型載入約需 20～40 秒。"""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if health():
                return True
            if self.proc is not None and self.proc.poll() is not None:
                self.error = f"翻譯伺服器結束了（exit {self.proc.returncode}），詳見 logs\\server.log"
                return False
            time.sleep(0.5)
        self.error = "翻譯伺服器太久沒有回應，詳見 logs\\server.log"
        return False

    def stop(self) -> None:
        if self.running:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        clear_pid(self.layout, "server")
        if self._log_file:
            self._log_file.close()
            self._log_file = None


# ── 只允許一個啟動器 ─────────────────────────────────────

class SingleInstance:
    """Windows 具名 mutex；第二次開啟時通知第一個把視窗叫出來，然後自己結束。"""

    NAME = "Local\\YomitokiLauncher"

    def __init__(self, layout: Layout):
        self.layout = layout
        self.handle = None
        self.request = pid_dir(layout) / "show.request"

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True
        import ctypes

        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.CreateMutexW(None, False, self.NAME)
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS

    def ask_existing_to_show(self) -> None:
        self.request.write_text(str(time.time()), encoding="ascii")

    def take_show_request(self) -> bool:
        if self.request.exists():
            self.request.unlink(missing_ok=True)
            return True
        return False
