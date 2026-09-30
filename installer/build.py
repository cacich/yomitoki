"""建置 Yomitoki 安裝檔：installer/build/Output/Yomitoki-Setup-<版本>.exe

步驟：
1. 建置網頁介面（ui/dist）
2. 把要安裝的檔案整理到 installer/build/stage/（program\ 與 bin\）
3. 下載固定版本的 uv，並核對 SHA-256
4. 用 Inno Setup 的 ISCC 編譯

需要：Node.js（建置介面）、Inno Setup 6（ISCC.exe；可用 --iscc 指定位置）

用法：python installer/build.py [--skip-ui] [--iscc D:\\tools\\InnoSetup\\ISCC.exe]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer"
BUILD = INSTALLER / "build"
STAGE = BUILD / "stage"
CACHE = BUILD / "cache"

UV_VERSION = "0.12.21"
UV_ZIP = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/uv-x86_64-pc-windows-msvc.zip"

# 要裝進 program\ 的檔案（相對 repo 根目錄）
PROGRAM_FILES = ["app", "assets", "extension", "requirements", "ui/dist", "installer/wheels",
                 "installer/bootstrap-launcher.cmd", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md",
                 "README.zh-TW.md", "pyproject.toml"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "*.test.mjs", ".cache")

ISCC_CANDIDATES = [Path(r"D:\tools\InnoSetup\ISCC.exe"), Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
                   Path(r"C:\Program Files\Inno Setup 6\ISCC.exe")]


def version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def build_ui() -> None:
    npm = shutil.which("npm")
    if not npm:
        sys.exit("找不到 npm：建置介面需要 Node.js（或用 --skip-ui 沿用現有的 ui/dist）")
    subprocess.run([npm, "run", "build"], cwd=ROOT / "ui", check=True, shell=sys.platform == "win32")


def stage_program() -> None:
    shutil.rmtree(STAGE, ignore_errors=True)
    program = STAGE / "program"
    for rel in PROGRAM_FILES:
        src = ROOT / rel
        dst = program / rel
        if not src.exists():
            sys.exit(f"缺少 {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=SKIP)
        else:
            shutil.copy2(src, dst)
    # Inno Setup 要 UTF-8 BOM 才能正確顯示中文
    for name in ("notice-zh.txt", "notice-en.txt"):
        text = (INSTALLER / name).read_text(encoding="utf-8")
        (STAGE / name).write_text(text, encoding="utf-8-sig")


def fetch_uv() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"uv-{UV_VERSION}.zip"
    if not cached.is_file():
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass
        with urllib.request.urlopen(UV_ZIP, timeout=120) as r:
            data = r.read()
        with urllib.request.urlopen(UV_ZIP + ".sha256", timeout=60) as r:
            expected = r.read().decode().split()[0].lower()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            sys.exit(f"uv 的 SHA-256 不符：{actual} ≠ {expected}")
        cached.write_bytes(data)
    (STAGE / "bin").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(cached.read_bytes())) as zf:
        name = next(n for n in zf.namelist() if n.endswith("uv.exe"))
        (STAGE / "bin" / "uv.exe").write_bytes(zf.read(name))


def find_iscc(given: str | None) -> Path:
    for p in [Path(given)] if given else ISCC_CANDIDATES:
        if p.is_file():
            return p
    found = shutil.which("iscc")
    if found:
        return Path(found)
    sys.exit("找不到 Inno Setup 的 ISCC.exe（用 --iscc 指定）")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-ui", action="store_true", help="不重新建置介面，直接用現有的 ui/dist")
    ap.add_argument("--iscc", help="ISCC.exe 的位置")
    args = ap.parse_args()

    v = version()
    if not args.skip_ui:
        print("建置介面…")
        build_ui()
    if not (ROOT / "ui" / "dist" / "index.html").is_file():
        sys.exit("ui/dist 不存在：先執行 npm run build")
    print("整理安裝檔案…")
    stage_program()
    print(f"下載 uv {UV_VERSION}…")
    fetch_uv()
    iscc = find_iscc(args.iscc)
    print(f"編譯安裝檔（{iscc}）…")
    subprocess.run([str(iscc), f"/DAppVersion={v}", str(INSTALLER / "yomitoki.iss")], check=True)
    out = BUILD / "Output" / f"Yomitoki-Setup-{v}.exe"
    print(f"完成：{out}（{out.stat().st_size / 2**20:.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
