"""把一張原始圖轉成所有需要的 ICO 與 PNG 尺寸。

來源預設走素材代號系統，所以使用者放在 文件\\Yomitoki\\custom-assets\\ 的
app-icon / app-icon-small / extension-icon / readme-hero 會自動被採用。
原始圖可以是 SVG（直接向量輸出每個尺寸），或 1024×1024 透明 PNG / WebP。

用法：
    python scripts/build-icons.py                 # 輸出到 assets/icons/
    python scripts/build-icons.py --source my.png # 指定主圖示原始圖
"""

from __future__ import annotations

import argparse
import io
import re
import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.assets import AssetRegistry  # noqa: E402

# 小於等於這個尺寸時改用簡化剪影（省略文字與抖動線條，避免糊成一團）
SMALL_MAX = 32

APP_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
TRAY_ICO_SIZES = (16, 32)
EXTENSION_SIZES = (16, 32, 48, 128)
SOCIAL_SIZE = (1280, 640)


def render(source: Path, width: int, height: int | None = None) -> Image.Image:
    """把 SVG / PNG / WebP 輸出成指定尺寸；尺寸不符時等比縮放、置中，不裁切也不變形。"""
    height = height or width
    if source.suffix.lower() == ".svg":
        import resvg_py

        svg = source.read_text(encoding="utf-8")
        w, h = _svg_size(svg)
        scale = min(width / w, height / h)
        png = resvg_py.svg_to_bytes(svg_string=svg, width=round(w * scale), height=round(h * scale))
        img = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    else:
        img = Image.open(source).convert("RGBA")
        scale = min(width / img.width, height / img.height)
        if abs(scale - 1) > 1e-6:
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((width - img.width) // 2, (height - img.height) // 2))
    return canvas


def _svg_size(svg: str) -> tuple[float, float]:
    m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
    if m:
        return float(m.group(1)), float(m.group(2))
    w = re.search(r'\bwidth="([\d.]+)', svg)
    h = re.search(r'\bheight="([\d.]+)', svg)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    raise ValueError("SVG 缺少 viewBox 或 width/height")


def write_ico(path: Path, images: list[Image.Image]) -> None:
    """寫出多尺寸 ICO；每個尺寸各自一張圖（PNG 壓縮，Windows Vista 以上支援）。"""
    entries = []
    for img in sorted(images, key=lambda i: i.width):
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        entries.append((img.width, img.height, buf.getvalue()))
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory, blobs = b"", b""
    for w, h, data in entries:
        directory += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    path.write_bytes(header + directory + blobs)


def build(out_dir: Path, sources: dict[str, Path]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def pick(size: int) -> Path:
        return sources["app-icon-small"] if size <= SMALL_MAX else sources["app-icon"]

    def save_png(img: Image.Image, rel: str) -> None:
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p, format="PNG", optimize=True)
        written.append(p)

    # Windows 應用程式與安裝檔
    write_ico(out_dir / "app.ico", [render(pick(s), s) for s in APP_ICO_SIZES])
    written.append(out_dir / "app.ico")
    # 系統匣
    write_ico(out_dir / "tray.ico", [render(sources["app-icon-small"], s) for s in TRAY_ICO_SIZES])
    written.append(out_dir / "tray.ico")
    # README 與一般用途的 PNG
    for s in (128, 256, 512):
        save_png(render(sources["app-icon"], s), f"app-icon-{s}.png")
    # Chrome 插件
    for s in EXTENSION_SIZES:
        save_png(render(sources["extension-icon"], s), f"extension/icon-{s}.png")
    # 網頁介面 favicon
    save_png(render(sources["app-icon-small"], 32), "favicon-32.png")
    save_png(render(sources["app-icon"], 180), "apple-touch-icon-180.png")
    small = sources["app-icon-small"]
    if small.suffix.lower() == ".svg":
        (out_dir / "favicon.svg").write_bytes(small.read_bytes())
        written.append(out_dir / "favicon.svg")
    # GitHub 社群預覽圖
    hero = render(sources["readme-hero"], *SOCIAL_SIZE)
    bg = Image.new("RGBA", SOCIAL_SIZE, (247, 240, 228, 255))
    bg.alpha_composite(hero)
    save_png(bg.convert("RGB"), "social-preview.png")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, help="主圖示原始圖（預設：素材代號 app-icon）")
    parser.add_argument("--small-source", type=Path, help="16/32 px 剪影（預設：app-icon-small）")
    parser.add_argument("--extension-source", type=Path, help="插件圖示（預設：extension-icon）")
    parser.add_argument("--hero", type=Path, help="社群預覽圖（預設：readme-hero）")
    parser.add_argument("--out", type=Path, default=ROOT / "assets" / "icons")
    args = parser.parse_args(argv)

    reg = AssetRegistry()
    sources = {
        "app-icon": args.source or reg.resolve("app-icon"),
        "app-icon-small": args.small_source or reg.resolve("app-icon-small"),
        "extension-icon": args.extension_source or reg.resolve("extension-icon"),
        "readme-hero": args.hero or reg.resolve("readme-hero"),
    }
    # 只換了主圖示、沒提供剪影時，小尺寸也用主圖示
    if args.source and not args.small_source:
        sources["app-icon-small"] = args.source
    for key, path in sources.items():
        if not Path(path).is_file():
            parser.error(f"{key} 的原始圖不存在：{path}")
        print(f"{key:<15} ← {path}")

    for p in build(args.out, sources):
        print(f"  wrote {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
