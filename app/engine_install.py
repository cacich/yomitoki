"""安裝 manga-image-translator 的原始碼（固定版本），並掛進某個 Python 環境的搜尋路徑。

上游的 setup.cfg 只打包最上層的 manga_translator，子套件不會被安裝，所以不能直接 pip install；
改成下載固定 commit 的原始碼，用 .pth 檔掛進 site-packages。
上游附帶、不可再散布的字型檔（msyh.ttc 等）會在解壓後刪除，Yomitoki 只用 Noto 字型。

依賴套件另外安裝（requirements/runtime.lock.txt）。這個模組只用標準函式庫，
啟動器環境（還沒有 torch 等套件）也能呼叫。
"""

from __future__ import annotations

import io
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

COMMIT = "441d07c59a735c7db3db2e7bb8b07920afd8a9cc"
URL = f"https://codeload.github.com/zyddnys/manga-image-translator/zip/{COMMIT}"
NON_REDISTRIBUTABLE_FONTS = ("msyh.ttc", "msgothic.ttc", "Arial-Unicode-Regular.ttf")
PTH_NAME = "yomitoki-manga-image-translator.pth"


def engine_dir(app_home: Path) -> Path:
    return Path(app_home) / "vendor" / f"manga-image-translator-{COMMIT[:7]}"


def download_source(app_home: Path, progress: Callable[[int, int | None], None] | None = None) -> Path:
    """下載並解壓固定版本的原始碼；已經有了就直接回傳路徑。"""
    target = engine_dir(app_home)
    if not (target / "manga_translator" / "__init__.py").is_file():
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass  # 啟動器環境沒有 truststore；Windows 版 Python 本來就會讀系統憑證庫
        buf = io.BytesIO()
        with urllib.request.urlopen(URL, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0) or None
            while chunk := resp.read(1 << 16):
                buf.write(chunk)
                if progress:
                    progress(buf.tell(), total)
        tmp = target.with_name(target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(buf) as zf:
            zf.extractall(tmp)
        (inner,) = list(tmp.iterdir())
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        inner.replace(target)
        shutil.rmtree(tmp, ignore_errors=True)
    for name in NON_REDISTRIBUTABLE_FONTS:
        (target / "fonts" / name).unlink(missing_ok=True)
    return target


def link_into(site_packages: Path, target: Path) -> Path:
    """在指定環境的 site-packages 放一個 .pth，讓 import manga_translator 找得到原始碼。"""
    pth = Path(site_packages) / PTH_NAME
    write_pth(pth, target)
    return pth


def write_pth(pth: Path, target: Path) -> None:
    """Python 3.11 以「系統地區編碼」（例如 cp950）讀 .pth，不是 UTF-8。

    路徑裡有中文（例如使用者名稱）時要用同一種編碼寫；系統編碼表示不了的字，
    改用 Windows 的 8.3 短路徑（全是 ASCII）。
    """
    import locale

    encoding = locale.getencoding() if hasattr(locale, "getencoding") else locale.getpreferredencoding(False)
    text = str(target)
    try:
        data = (text + "\n").encode(encoding)
    except UnicodeEncodeError:
        text = _short_path(target) or text
        data = (text + "\n").encode(encoding, errors="replace")
    Path(pth).write_bytes(data)


def _short_path(path: Path) -> str | None:
    import sys

    if sys.platform != "win32":
        return None
    import ctypes

    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 1024)
    return buf.value if 0 < n < 1024 and buf.value.isascii() else None
