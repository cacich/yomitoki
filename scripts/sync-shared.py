"""把共用的檔案複製到各個只能讀自己資料夾的地方。

- Chrome 插件（extension/）：載入未封裝的插件時，只能讀取 extension/ 裡的檔案
  - 設計 token：ui/src/styles/tokens.css → extension/tokens.css
  - 圖示：assets/icons/extension/icon-*.png → extension/icons/
- 首次啟動精靈（app/launcher/web/）：pywebview 只提供這個資料夾裡的檔案
  - 設計 token：ui/src/styles/tokens.css → app/launcher/web/tokens.css

複製出來的檔案會一起 commit，clone 下來就能直接用。
tests/test_extension.py 與 tests/test_launcher.py 會檢查兩邊是否一致；改了 token 或圖示後重跑這支腳本。

用法：python scripts/sync-shared.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "extension"

TOKENS = ROOT / "ui" / "src" / "styles" / "tokens.css"
COPIES = [(TOKENS, EXT / "tokens.css"), (TOKENS, ROOT / "app" / "launcher" / "web" / "tokens.css")] + [
    (ROOT / "assets" / "icons" / "extension" / f"icon-{s}.png", EXT / "icons" / f"icon-{s}.png") for s in (16, 32, 48, 128)
]


def main() -> int:
    for src, dst in COPIES:
        if not src.is_file():
            print(f"找不到 {src.relative_to(ROOT)}；圖示請先執行 scripts/build-icons.py")
            return 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"  {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
