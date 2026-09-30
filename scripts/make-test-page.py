"""產生原創的日文漫畫測試頁（tests/fixtures/ja-page-01.png）。

測試與範例一律使用自己畫的圖：這裡用 Yomitoki 的預設狸貓插畫，
搭配自己寫的日文台詞，排成四格、直書對話框、由右至左閱讀。
台詞與閱讀順序另存成 ja-page-01.expected.json，給 OCR 測試比對。

用法：python scripts/make-test-page.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import fonts  # noqa: E402

OUT = ROOT / "tests" / "fixtures"
W, H = 1200, 1700
MARGIN, GUTTER, BORDER = 50, 24, 6

# (分格, 插畫, 插畫位置與大小, 對話框中心與大小, 台詞)；台詞順序即閱讀順序
PANELS = [
    ((MARGIN, MARGIN, W - MARGIN, 600), "mascot-welcome", (80, 90, 500)),
    ((W // 2 + GUTTER // 2, 600 + GUTTER, W - MARGIN, 1140), "mascot-guide", (620, 690, 400)),
    ((MARGIN, 600 + GUTTER, W // 2 - GUTTER // 2, 1140), "mascot-error", (60, 720, 380)),
    ((MARGIN, 1140 + GUTTER, W - MARGIN, H - MARGIN), "mascot-loading", (90, 1190, 440)),
]
# (對話框中心, 每一欄的文字)；清單順序即閱讀順序（由右至左、由上而下）
BUBBLES = [
    ((1060, 250), ["おはよう！"]),
    ((860, 330), ["今日は新しい", "漫画を読むよ"]),
    ((1060, 780), ["でも…"]),
    ((860, 950), ["日本語が", "むずかしい"]),
    ((470, 860), ["この字", "なんて読むの？"]),
    ((1030, 1400), ["よみときに", "任せて！"]),
    ((780, 1410), ["ぜんぶ読める", "ようになった！"]),
]
FONT_SIZE = 38
ROTATE = set("「」ー…〜（）─")
SMALL_PUNCT = set("、。")


def render_asset(asset_id: str, size: int) -> Image.Image:
    import resvg_py

    svg = ROOT / "assets" / "defaults" / f"{asset_id}.svg"
    png = resvg_py.svg_to_bytes(svg_path=str(svg), width=size, height=size)
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


STEP, COL_W = int(FONT_SIZE * 1.08), int(FONT_SIZE * 1.3)


def bubble_radii(cols: list[str]) -> tuple[int, int]:
    return COL_W * len(cols) // 2 + 55, STEP * max(len(c) for c in cols) // 2 + 60


def draw_vertical(img: Image.Image, cols: list[str], center: tuple[int, int], font: ImageFont.FreeTypeFont) -> None:
    """直書：字由上而下、欄由右而左。"""
    step, col_w = STEP, COL_W
    total_w = col_w * len(cols)
    total_h = step * max(len(c) for c in cols)
    x0 = center[0] + total_w // 2 - col_w
    y0 = center[1] - total_h // 2
    draw = ImageDraw.Draw(img)
    for ci, col in enumerate(cols):
        x = x0 - ci * col_w + (col_w - FONT_SIZE) // 2
        for ri, ch in enumerate(col):
            y = y0 + ri * step
            if ch in ROTATE:
                glyph = Image.new("L", (FONT_SIZE * 2, FONT_SIZE * 2), 0)
                ImageDraw.Draw(glyph).text((FONT_SIZE // 2, FONT_SIZE // 2), ch, font=font, fill=255)
                glyph = glyph.rotate(-90, resample=Image.BICUBIC)
                bbox = glyph.getbbox() or (0, 0, 1, 1)
                glyph = glyph.crop(bbox)
                gx = x + (FONT_SIZE - glyph.width) // 2
                gy = y + (FONT_SIZE - glyph.height) // 2
                img.paste((20, 20, 20), (gx, gy), glyph)
            elif ch in SMALL_PUNCT:
                draw.text((x + FONT_SIZE * 0.55, y - FONT_SIZE * 0.45), ch, font=font, fill=(20, 20, 20))
            else:
                draw.text((x, y), ch, font=font, fill=(20, 20, 20))


def main() -> int:
    font = ImageFont.truetype(str(fonts.ensure("noto-sans-jp")), FONT_SIZE)
    page = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(page)

    for (x1, y1, x2, y2), asset_id, (ax, ay, size) in PANELS:
        tile = Image.new("RGB", (x2 - x1, y2 - y1), (250, 247, 240))
        page.paste(tile, (x1, y1))
        art = render_asset(asset_id, size)
        page.paste(art, (ax, ay), art)
        draw.rectangle((x1, y1, x2, y2), outline="black", width=BORDER)

    for (cx, cy), cols in BUBBLES:
        rx, ry = bubble_radii(cols)
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill="white", outline="black", width=4)
        draw_vertical(page, cols, (cx, cy), font)

    OUT.mkdir(parents=True, exist_ok=True)
    page.save(OUT / "ja-page-01.png", optimize=True)
    expected = {"source_lang": "ja", "lines": ["".join(cols) for _, cols in BUBBLES]}
    (OUT / "ja-page-01.expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'ja-page-01.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
