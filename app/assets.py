"""可替換素材：介面只透過代號讀取圖片，不在程式裡寫死檔名。

讀取順序：
1. 使用者自訂資料夾 文件\\Yomitoki\\custom-assets\\<代號>.<svg|png|webp>
2. repo 內建的預設素材 assets/defaults/

用法：
    from app.assets import asset
    asset("mascot-welcome")          # -> Path
"""

from __future__ import annotations

import json
import shutil
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import paths

SUPPORTED_FORMATS = ("svg", "png", "webp")


class UnknownAssetError(KeyError):
    pass


class UnsupportedFormatError(ValueError):
    pass


@dataclass(frozen=True)
class AssetSpec:
    id: str
    purpose: str
    purpose_en: str
    size: tuple[int, int]
    background: str
    default: str
    animated: bool = False
    tileable: bool = False


@dataclass
class AssetInfo:
    """設定頁「外觀素材」區塊需要的資訊。"""

    spec: AssetSpec
    path: Path
    source: str  # "custom" | "default"
    format: str
    pixel_size: tuple[int, int] | None
    warnings: list[str] = field(default_factory=list)


class AssetRegistry:
    def __init__(self, builtin_dir: Path | None = None, custom_dir: Path | None = None):
        self.builtin_dir = Path(builtin_dir) if builtin_dir else paths.BUILTIN_ASSETS_DIR
        self._custom_dir = Path(custom_dir) if custom_dir else None
        manifest = json.loads((self.builtin_dir / "manifest.json").read_text(encoding="utf-8"))
        self.specs: dict[str, AssetSpec] = {
            key: AssetSpec(
                id=key,
                purpose=v["purpose"],
                purpose_en=v.get("purpose_en", ""),
                size=tuple(v["size"]),
                background=v["background"],
                default=v["default"],
                animated=v.get("animated", False),
                tileable=v.get("tileable", False),
            )
            for key, v in manifest["assets"].items()
        }

    @property
    def custom_dir(self) -> Path:
        return self._custom_dir if self._custom_dir else paths.custom_assets_dir()

    def spec(self, asset_id: str) -> AssetSpec:
        try:
            return self.specs[asset_id]
        except KeyError:
            raise UnknownAssetError(asset_id) from None

    def default_path(self, asset_id: str) -> Path:
        return self.builtin_dir / self.spec(asset_id).default

    def custom_path(self, asset_id: str) -> Path | None:
        """使用者自訂的檔案；同代號有多個格式時，取最後修改的那個。"""
        self.spec(asset_id)
        if not self.custom_dir.is_dir():
            return None
        candidates = [
            p for ext in SUPPORTED_FORMATS if (p := self.custom_dir / f"{asset_id}.{ext}").is_file()
        ]
        return max(candidates, key=lambda p: p.stat().st_mtime_ns) if candidates else None

    def resolve(self, asset_id: str) -> Path:
        return self.custom_path(asset_id) or self.default_path(asset_id)

    def inspect(self, asset_id: str) -> AssetInfo:
        spec = self.spec(asset_id)
        custom = self.custom_path(asset_id)
        path = custom or self.default_path(asset_id)
        fmt = path.suffix.lstrip(".").lower()
        pixel_size = image_size(path)
        warnings: list[str] = []
        if pixel_size and fmt != "svg":
            w, h = pixel_size
            rw, rh = spec.size
            if w < rw or h < rh:
                warnings.append(f"解析度 {w}×{h} 低於建議的 {rw}×{rh}，在高解析度螢幕上可能模糊")
            if abs(w / h - rw / rh) > 0.02:
                warnings.append(f"比例與建議的 {rw}:{rh} 不同，會等比縮放並置中顯示")
        return AssetInfo(spec, path, "custom" if custom else "default", fmt, pixel_size, warnings)

    def replace(self, asset_id: str, source: Path) -> Path:
        """把使用者提供的圖片複製進自訂資料夾，取代目前的素材。"""
        self.spec(asset_id)
        source = Path(source)
        fmt = source.suffix.lstrip(".").lower()
        if fmt not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(f"只支援 {', '.join(SUPPORTED_FORMATS)}，收到 .{fmt}")
        if sniff_format(source) != fmt:
            raise UnsupportedFormatError(f"{source.name} 的內容不是有效的 {fmt.upper()} 檔")
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self._remove_custom(asset_id)
        target = self.custom_dir / f"{asset_id}.{fmt}"
        shutil.copyfile(source, target)
        return target

    def restore_default(self, asset_id: str) -> None:
        self.spec(asset_id)
        self._remove_custom(asset_id)

    def _remove_custom(self, asset_id: str) -> None:
        for ext in SUPPORTED_FORMATS:
            (self.custom_dir / f"{asset_id}.{ext}").unlink(missing_ok=True)


def sniff_format(path: Path) -> str | None:
    head = Path(path).read_bytes()[:512]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    text = head.lstrip(b"\xef\xbb\xbf").lstrip()
    if text.startswith(b"<svg") or (text.startswith(b"<?xml") and b"<svg" in Path(path).read_bytes()[:4096]):
        return "svg"
    return None


def image_size(path: Path) -> tuple[int, int] | None:
    """讀取 PNG / WebP 的像素尺寸（不需要 Pillow）；SVG 回傳 None。"""
    data = Path(path).read_bytes()[:64]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X":
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return w, h
        if chunk == b"VP8L":
            b = int.from_bytes(data[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
    return None


@lru_cache(maxsize=1)
def registry() -> AssetRegistry:
    return AssetRegistry()


def asset(asset_id: str) -> Path:
    return registry().resolve(asset_id)
