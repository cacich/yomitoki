"""嵌字字型：首次使用時下載到 %LOCALAPPDATA%\\Yomitoki\\fonts\\。

只使用 OFL 授權、可再散布的字型；授權檔一併下載放在字型旁邊。
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

from . import paths
from .languages import FONTS, FontSpec, TargetLanguage

log = logging.getLogger("yomitoki.fonts")

OFL_URL = "https://github.com/notofonts/noto-cjk/raw/Sans2.004/LICENSE"

# 介面字型（中文）：jf open 粉圓 2.1，OFL-1.1。英文介面字型由前端的 @fontsource 套件打包。
UI_FONTS: dict[str, FontSpec] = {
    "jf-openhuninn": FontSpec(
        "jf-openhuninn", "jf-openhuninn-2.1.ttf",
        "https://github.com/justfont/open-huninn-font/raw/v2.1/font/jf-openhuninn-2.1.ttf",
    ),
}
HUNINN_LICENSE_URL = "https://github.com/justfont/open-huninn-font/raw/v2.1/LICENSE"


def ensure_ui_font(font_id: str) -> Path:
    spec = UI_FONTS[font_id]
    target = font_path(spec)
    if not (target.is_file() and target.stat().st_size > 0):
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info("下載介面字型 %s …", spec.filename)
        _download(spec.url, target)
        _download(HUNINN_LICENSE_URL, target.parent / "jf-openhuninn-LICENSE.txt")
    return target


def font_path(spec: FontSpec) -> Path:
    return paths.fonts_dir() / spec.filename


def ensure(font_id: str) -> Path:
    spec = FONTS[font_id]
    target = font_path(spec)
    if target.is_file() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("下載字型 %s …", spec.filename)
    _download(spec.url, target)
    license_file = target.parent / "Noto-CJK-OFL.txt"
    if not license_file.exists():
        _download(OFL_URL, license_file)
    return target


def ensure_for_target(target: TargetLanguage) -> tuple[Path, list[Path]]:
    return ensure(target.font), [ensure(f) for f in target.fallback_fonts]


def _download(url: str, dest: Path) -> None:
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as f:
        while chunk := resp.read(1 << 16):
            f.write(chunk)
    tmp.replace(dest)
