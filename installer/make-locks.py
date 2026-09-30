"""從一個已驗證可用的開發環境產生安裝檔用的版本鎖定檔。

    requirements/runtime.lock.txt   執行環境（翻譯核心）的所有套件，版本全部固定
    requirements/launcher.lock.txt  啟動器環境（視窗、系統匣）的套件

安裝時以 --no-deps 安裝鎖定檔，所以每個人裝到的版本都跟這台驗證過的一樣。
PyTorch 另外依顯示卡從 CUDA 或 CPU 的 index 安裝，不寫在鎖定檔裡。

用法：python installer/make-locks.py [開發環境的 python.exe]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "requirements"

# 開發工具與 PyTorch 不進執行環境的鎖定檔
EXCLUDE = {"torch", "torchvision", "yomitoki", "py-spy", "pytest", "iniconfig", "pluggy", "resvg-py"}
# rusty-manga-image-translator 只在這個 index 上有 wheel
EXTRA_INDEX = "https://frederik-uni.github.io/manga-image-translator-rust/python/wheels/simple/"

LAUNCHER = [
    "pywebview==6.2.1", "pythonnet==3.2.0", "clr-loader==0.3.1", "cffi==2.1.1", "pycparser==3.0",
    "proxy-tools==0.1.0", "bottle==0.13.4", "typing-extensions==4.16.0",
    "pystray==0.19.5", "six==1.17.0", "pillow==12.3.0",
]


def freeze(python: str) -> list[str]:
    uv = shutil.which("uv")
    if not uv:
        sys.exit("找不到 uv")
    out = subprocess.run([uv, "pip", "freeze", "--python", python], capture_output=True, text=True, check=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def main() -> int:
    python = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / ".venv" / "Scripts" / "python.exe")
    lines = []
    for line in freeze(python):
        if line.startswith("-e ") or "@ file:" in line:
            continue
        name = line.split("==")[0].lower()
        if name in EXCLUDE:
            continue
        lines.append(line)
    header = [
        "# 執行環境的完整套件清單（由 installer/make-locks.py 產生，請勿手動修改）",
        "# 以 --no-deps 安裝；PyTorch 另外依顯示卡安裝。",
        f"--extra-index-url {EXTRA_INDEX}",
        "",
    ]
    (REQ / "runtime.lock.txt").write_text("\n".join(header + sorted(lines, key=str.lower)) + "\n", encoding="utf-8")
    (REQ / "launcher.lock.txt").write_text(
        "# 啟動器環境（視窗、系統匣、首次啟動精靈），以 --no-deps 安裝\n" + "\n".join(LAUNCHER) + "\n", encoding="utf-8")
    print(f"runtime.lock.txt：{len(lines)} 個套件；launcher.lock.txt：{len(LAUNCHER)} 個套件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
