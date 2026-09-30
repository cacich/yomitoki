"""首次啟動精靈的「下載元件」：用 uv 建立執行環境、安裝翻譯核心、下載模型。

安裝後的資料夾（預設 %LOCALAPPDATA%\\Yomitoki）：

    program\\           程式本身（安裝檔放進來的）
    bin\\uv.exe         Python 環境管理工具
    python\\            uv 下載的 Python 3.11
    env\\launcher\\     啟動器環境：視窗、系統匣、這個精靈（安裝檔建立，很小）
    env\\runtime\\      執行環境：PyTorch、manga-image-translator、Yomitoki（精靈建立，數 GB）
    models\\ fonts\\ vendor\\   模型、字型、manga-image-translator 原始碼
    cache\\uv\\         下載快取，安裝完成後清掉
    logs\\              記錄檔

只用標準函式庫：精靈執行時，執行環境還不存在。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import engine_install

PYTHON_VERSION = "3.11.16"
TORCH = {"cuda": ("torch==2.14.0+cu126", "torchvision==0.29.0+cu126", "https://download.pytorch.org/whl/cu126"),
         "cpu": ("torch==2.14.0+cpu", "torchvision==0.29.0+cpu", "https://download.pytorch.org/whl/cpu")}
# 下載量估計，用來顯示進度（2026-09 實測；實際大小依版本略有不同）
# 套件裡最大的是 manga-ocr 用的日文辭典 unidic-lite（解開後約 540 MB，而且要在本機打包，比較慢）
TORCH_DOWNLOAD_BYTES = {"cuda": 2_200_000_000, "cpu": 260_000_000}
PACKAGES_DOWNLOAD_BYTES = 1_900_000_000
# 模型從 GitHub Release 與 Hugging Face 下載，偶爾會在中途斷線；上游的下載器會從 .part 續傳
MODEL_ATTEMPTS = 5
# 需要的磁碟空間（GB）：套件 + 模型 + 安裝過程中的下載快取
REQUIRED_GB = {"cuda": 12, "cpu": 6}
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class Layout:
    root: Path
    program: Path

    @classmethod
    def installed(cls, root: Path) -> "Layout":
        return cls(Path(root), Path(root) / "program")

    @property
    def uv(self) -> Path:
        bundled = self.root / "bin" / "uv.exe"
        return bundled if bundled.is_file() else Path(shutil.which("uv") or bundled)

    python_dir = property(lambda self: self.root / "python")
    cache = property(lambda self: self.root / "cache" / "uv")
    runtime_env = property(lambda self: self.root / "env" / "runtime")
    logs = property(lambda self: self.root / "logs")
    wheels = property(lambda self: self.program / "installer" / "wheels")
    runtime_lock = property(lambda self: self.program / "requirements" / "runtime.lock.txt")
    marker = property(lambda self: self.runtime_env / "yomitoki-ready.json")

    @property
    def runtime_python(self) -> Path:
        return self.runtime_env / "Scripts" / "python.exe" if sys.platform == "win32" else self.runtime_env / "bin" / "python"

    @property
    def runtime_site(self) -> Path:
        return self.runtime_env / "Lib" / "site-packages"


def lock_hash(layout: Layout) -> str:
    return hashlib.sha1(layout.runtime_lock.read_bytes()).hexdigest()[:12]


def is_ready(layout: Layout) -> bool:
    """執行環境已經裝好，而且跟目前程式要的版本一致（更新程式後鎖定檔變了就要重裝）。"""
    try:
        info = json.loads(layout.marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return info.get("lock") == lock_hash(layout) and layout.runtime_python.is_file()


# ── 環境檢查 ─────────────────────────────────────────────────

def detect_gpu() -> dict:
    """用 nvidia-smi 偵測 NVIDIA 顯示卡（不需要 PyTorch）。"""
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW).stdout
            name, mem = [s.strip() for s in out.strip().splitlines()[0].split(",")]
            return {"nvidia": True, "name": name, "vram_gb": round(int(mem) / 1024, 1)}
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass
    return {"nvidia": False, "name": None, "vram_gb": None}


def environment_check(layout: Layout) -> dict:
    gpu = detect_gpu()
    device = "cuda" if gpu["nvidia"] else "cpu"
    layout.root.mkdir(parents=True, exist_ok=True)
    free_gb = round(shutil.disk_usage(layout.root).free / 2**30, 1)
    return {"gpu": gpu, "device": device, "free_gb": free_gb, "required_gb": REQUIRED_GB[device],
            "disk_ok": free_gb >= REQUIRED_GB[device], "root": str(layout.root)}


# ── 安裝 ─────────────────────────────────────────────────────

@dataclass
class StepInfo:
    key: str
    weight: float  # 占整體進度的比例


# 比例依實測時間：套件約 20 分鐘、PyTorch 約 4 分鐘、模型視 GitHub 的速度 5～30 分鐘
STEPS = [StepInfo("python", 0.02), StepInfo("venv", 0.01), StepInfo("packages", 0.37), StepInfo("torch", 0.2),
         StepInfo("engine", 0.03), StepInfo("models", 0.35), StepInfo("finish", 0.02)]


@dataclass
class Progress:
    status: str = "idle"          # idle | running | done | error
    step: str | None = None
    fraction: float = 0.0         # 0～1，整體進度
    detail: str = ""              # 目前的輸出，例如下載中的檔案
    downloaded_mb: int = 0
    error: str | None = None
    log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["log"] = self.log[-12:]
        return d


class RuntimeInstaller:
    def __init__(self, layout: Layout, device: str, runner: Callable | None = None):
        if device not in TORCH:
            raise ValueError(device)
        self.layout = layout
        self.device = device
        self.progress = Progress()
        self._run = runner or self._run_process
        self._thread: threading.Thread | None = None

    # 給精靈呼叫：在背景執行緒安裝
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.progress = Progress(status="running")
        self._thread = threading.Thread(target=self.run, name="yomitoki-bootstrap", daemon=True)
        self._thread.start()

    def run(self) -> None:
        self.progress.status = "running"
        self.layout.logs.mkdir(parents=True, exist_ok=True)
        done = 0.0
        try:
            for step in STEPS:
                self.progress.step = step.key
                getattr(self, f"_step_{step.key}")(done, step.weight)
                done += step.weight
                self.progress.fraction = min(1.0, done)
            self.progress.status = "done"
            self.progress.detail = ""
        except Exception as e:  # noqa: BLE001 — 任何錯誤都要顯示在精靈裡
            self.progress.status = "error"
            self.progress.error = str(e) or type(e).__name__
            self._log(f"錯誤：{self.progress.error}")

    # ── 各步驟 ──
    def _step_python(self, base, weight):
        self._uv(["python", "install", PYTHON_VERSION, "--no-registry", "--no-bin"])
        if not self._python_exe():
            raise RuntimeError(f"Python {PYTHON_VERSION} 沒有安裝成功")

    def _step_venv(self, base, weight):
        python = self._python_exe()
        self._uv(["venv", "--python", str(python), "--allow-existing", str(self.layout.runtime_env)])
        pin_venv_home(self.layout.runtime_env / "pyvenv.cfg", python.parent)

    def _step_packages(self, base, weight):
        env = {"PYTHONUTF8": "1", "UV_INSECURE_NO_ZIP_VALIDATION": "1"}
        self._with_download_meter(base, weight, PACKAGES_DOWNLOAD_BYTES, lambda: self._uv(
            ["pip", "install", "--python", str(self.layout.runtime_python), "--no-deps",
             "-r", str(self.layout.runtime_lock), "--find-links", str(self.layout.wheels)], env))

    def _step_torch(self, base, weight):
        torch, vision, index = TORCH[self.device]
        self._with_download_meter(base, weight, TORCH_DOWNLOAD_BYTES[self.device], lambda: self._uv(
            ["pip", "install", "--python", str(self.layout.runtime_python), "--no-deps", torch, vision,
             "--index-url", index]))

    def _step_engine(self, base, weight):
        def report(got, total):
            self.progress.detail = f"manga-image-translator {got // 2**20} MB"
            if total:
                self.progress.fraction = base + weight * min(1.0, got / total)
        target = engine_install.download_source(self.layout.root, report)
        engine_install.link_into(self.layout.runtime_site, target)

    def _step_models(self, base, weight):
        # 在執行環境裡跑 yomitoki setup：下載偵測、OCR、擦字模型與嵌字字型
        started = time.monotonic()
        last = {"line": "載入翻譯核心"}

        def on_line(line):
            if "Downloading" in line or "下載" in line or "Verifying" in line:
                # 三組模型 + 字型，每出現一次就往前推一點
                self.progress.fraction = min(base + weight * 0.95, self.progress.fraction + weight * 0.12)
            last["line"] = line[:120]

        # 第一次 import PyTorch 與 manga-image-translator 要好幾分鐘、而且不會輸出任何東西；
        # 每秒更新經過的時間，精靈才不會看起來像當掉
        stop = threading.Event()

        def ticker():
            while not stop.wait(1.0):
                self.progress.detail = f"{last['line']}（{time.monotonic() - started:.0f} 秒）"

        t = threading.Thread(target=ticker, daemon=True)
        t.start()
        try:
            for attempt in range(1, MODEL_ATTEMPTS + 1):
                try:
                    # 在 program\ 裡執行：python -m app 會從目前資料夾找到 Yomitoki 本身，不需要 .pth
                    self._run([str(self.layout.runtime_python), "-m", "app", "setup", "--device", self.device],
                              self._env(), on_line, cwd=self.layout.program)
                    break
                except RuntimeError:
                    if attempt == MODEL_ATTEMPTS:
                        raise
                    self._log(f"模型下載中斷，{5 * attempt} 秒後重試（第 {attempt + 1}/{MODEL_ATTEMPTS} 次）")
                    last["line"] = f"連線中斷，重新連線中（第 {attempt + 1}/{MODEL_ATTEMPTS} 次）"
                    time.sleep(5 * attempt)
        finally:
            stop.set()
            t.join(timeout=2)

    def _step_finish(self, base, weight):
        info = {"lock": lock_hash(self.layout), "device": self.device, "python": PYTHON_VERSION,
                "torch": TORCH[self.device][0], "installed": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.layout.marker.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        # 清掉下載快取（PyTorch 的 wheel 就有好幾 GB）
        shutil.rmtree(self.layout.cache.parent, ignore_errors=True)

    # ── 工具 ──
    def _python_exe(self) -> Path | None:
        name = "python.exe" if sys.platform == "win32" else "bin/python3"
        found = sorted(self.layout.python_dir.glob(f"cpython-{PYTHON_VERSION}-*/{name}"))
        return found[0] if found else None

    def _env(self, extra: dict | None = None) -> dict:
        env = dict(os.environ)
        env.update({
            "UV_PYTHON_INSTALL_DIR": str(self.layout.python_dir),
            "UV_CACHE_DIR": str(self.layout.cache),
            "UV_SYSTEM_CERTS": "1",          # 公司網路常用自己的憑證攔截 HTTPS
            "UV_LINK_MODE": "copy",
            "UV_PYTHON_PREFERENCE": "only-managed",
            "UV_NO_PROGRESS": "1",
            "YOMITOKI_APP_HOME": str(self.layout.root),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        env.update(extra or {})
        return env

    def _uv(self, args: list[str], extra_env: dict | None = None) -> None:
        self._run([str(self.layout.uv), *args], self._env(extra_env), lambda line: setattr(self.progress, "detail", line[:160]))

    def _with_download_meter(self, base, weight, expected_bytes, action):
        """uv 沒有可讀的進度輸出；用下載快取資料夾的大小估計進度。"""
        stop = threading.Event()
        start_size = _dir_size(self.layout.cache)

        def meter():
            while not stop.wait(1.0):
                got = max(0, _dir_size(self.layout.cache) - start_size)
                self.progress.downloaded_mb = got // 2**20
                self.progress.fraction = base + weight * min(0.97, got / expected_bytes)

        t = threading.Thread(target=meter, daemon=True)
        t.start()
        try:
            action()
        finally:
            stop.set()
            t.join(timeout=2)

    def _log(self, line: str) -> None:
        self.progress.log.append(line)
        try:
            with (self.layout.logs / "setup.log").open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} {line}\n")
        except OSError:
            pass

    def _run_process(self, cmd: list[str], env: dict, on_line: Callable[[str], None], cwd: Path | None = None) -> None:
        self._log("$ " + " ".join(_short(c) for c in cmd))
        proc = subprocess.Popen(cmd, env=env, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW)
        tail: list[str] = []
        for raw in proc.stdout:
            for line in re.split(r"[\r\n]+", raw):
                line = line.strip()
                if line:
                    tail = (tail + [line])[-20:]
                    self._log(line)
                    on_line(line)
        if proc.wait() != 0:
            raise RuntimeError(f"{Path(cmd[0]).name} 執行失敗（exit {proc.returncode}）：{' / '.join(tail[-3:])}")


def pin_venv_home(cfg: Path, python_dir: Path) -> None:
    """uv 讓環境指向「次版本」的 junction（cpython-3.11-…），方便之後升級修補版本。

    但開啟 RedirectionGuard 的程序不允許穿過一般使用者建立的 junction
    （os error 448：路徑包含不受信任的掛接點；Inno Setup 6.5 起預設會開），
    所以改成直接指向實際的資料夾（cpython-3.11.16-…），不管在哪種情況下都能用。
    """
    lines = [ln for ln in cfg.read_text(encoding="utf-8").splitlines() if not ln.startswith("home =")]
    cfg.write_text("\n".join([f"home = {python_dir}", *lines]) + "\n", encoding="utf-8")


def _short(arg: str) -> str:
    return Path(arg).name if len(arg) > 60 and ("\\" in arg or "/" in arg) else arg


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def runtime_server_command(layout: Layout, port: int = 8765) -> list[str]:
    return [str(layout.runtime_python), "-m", "app", "serve", "--port", str(port)]
