"""安裝 manga-image-translator 的原始碼（固定版本），並加進目前 Python 環境的搜尋路徑。

上游的 setup.cfg 只打包最上層的 manga_translator，子套件不會被安裝，
所以不能直接 pip install；改成下載固定 commit 的原始碼，用 .pth 檔掛進 site-packages。
上游附帶、不可再散布的字型檔（msyh.ttc 等）會在解壓後刪除，Yomitoki 只用 Noto 字型。

依賴套件另外安裝：uv pip install -r requirements/mit.txt

用法：python scripts/install-engine.py
"""

from __future__ import annotations

import io
import shutil
import site
import sys
import sysconfig
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import paths  # noqa: E402

COMMIT = "441d07c59a735c7db3db2e7bb8b07920afd8a9cc"
URL = f"https://codeload.github.com/zyddnys/manga-image-translator/zip/{COMMIT}"
NON_REDISTRIBUTABLE_FONTS = ("msyh.ttc", "msgothic.ttc", "Arial-Unicode-Regular.ttf")
PTH_NAME = "yomitoki-manga-image-translator.pth"


def main() -> int:
    target = paths.app_home() / "vendor" / f"manga-image-translator-{COMMIT[:7]}"
    if not (target / "manga_translator" / "__init__.py").is_file():
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass
        print(f"下載 manga-image-translator@{COMMIT[:7]} …")
        with urllib.request.urlopen(URL, timeout=120) as resp:
            data = resp.read()
        tmp = target.with_name(target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tmp)
        (inner,) = list(tmp.iterdir())
        shutil.rmtree(target, ignore_errors=True)
        inner.replace(target)
        shutil.rmtree(tmp, ignore_errors=True)
    for name in NON_REDISTRIBUTABLE_FONTS:
        (target / "fonts" / name).unlink(missing_ok=True)

    site_dir = Path(sysconfig.get_paths()["purelib"])
    if not site_dir.is_dir():
        site_dir = Path(site.getsitepackages()[0])
    (site_dir / PTH_NAME).write_text(str(target) + "\n", encoding="utf-8")
    print(f"已安裝到 {target}")
    print(f"搜尋路徑：{site_dir / PTH_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
