"""開發環境用：把 manga-image-translator 的原始碼（固定版本）掛進目前的 Python 環境。

實際邏輯在 app/engine_install.py（安裝檔的首次啟動精靈也用同一套）。
依賴套件另外安裝：uv pip install -r requirements/mit.txt

用法：python scripts/install-engine.py
"""

from __future__ import annotations

import site
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import engine_install, paths  # noqa: E402


def main() -> int:
    print(f"安裝 manga-image-translator@{engine_install.COMMIT[:7]} …")
    target = engine_install.download_source(paths.app_home())
    site_dir = Path(sysconfig.get_paths()["purelib"])
    if not site_dir.is_dir():
        site_dir = Path(site.getsitepackages()[0])
    pth = engine_install.link_into(site_dir, target)
    print(f"已安裝到 {target}")
    print(f"搜尋路徑：{pth}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
