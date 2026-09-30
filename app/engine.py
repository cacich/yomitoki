"""包裝 manga-image-translator 的偵測、OCR、擦字與嵌字。

我們不走它的完整流程，而是逐步呼叫各階段：
    偵測 → OCR → 合併成對話框 → 排閱讀順序      → Page JSON（原文、座標、閱讀順序）
    Page JSON（含譯文）→ 遮罩 → 擦字 → 嵌字     → 譯圖
中間的翻譯交給 Claude Code，所以 OCR 只需要跑一次；改譯名時只重做嵌字。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from . import fonts, paths
from .languages import SourceLanguage, TargetLanguage
from .page import Page, Region

log = logging.getLogger("yomitoki.engine")


@dataclass
class EngineSettings:
    device: str = "auto"                 # auto | cuda | cpu
    detector: str = "default"
    detection_size: int = 2048
    text_threshold: float = 0.5
    box_threshold: float = 0.7
    unclip_ratio: float = 2.3
    inpainter: str = "lama_large"
    inpainting_size: int | None = None   # None = 依顯示卡記憶體自動決定（見 auto_inpainting_size）
    mask_dilation_offset: int = 20


def auto_inpainting_size(device: str, vram_gb: float | None) -> int:
    """擦字尺寸決定顯示卡記憶體峰值。實測 GTX 1650（4 GB）：1536 峰值 4.3 GB、超過實體容量，
    整台電腦會變卡；1024 峰值 2.7 GB、品質看不出差別，而且比較快。"""
    if device != "cuda" or not vram_gb:
        return 1024
    if vram_gb <= 4.5:
        return 1024
    if vram_gb <= 8.5:
        return 1536
    return 2048


def gpu_memory_gb() -> float | None:
    import torch

    if not torch.cuda.is_available():
        return None
    return torch.cuda.get_device_properties(0).total_memory / 2**30


def release_gpu_memory() -> None:
    """把 PyTorch 快取的顯示卡記憶體還給系統。

    這張顯示卡通常也負責桌面與瀏覽器的畫面；翻譯完不釋放，閒置時也會一直佔著 3～4 GB，
    其他程式只好把畫面資料搬到一般記憶體，整台電腦就會變卡。模型本身留在顯示卡上（約 1.1 GB）。
    """
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _bootstrap() -> None:
    """匯入 manga-image-translator 前的環境設定（只做一次）。"""
    if getattr(_bootstrap, "done", False):
        return
    models = paths.models_dir()
    models.mkdir(parents=True, exist_ok=True)
    # Hugging Face 模型（manga-ocr）也放在同一個資料夾
    os.environ.setdefault("HF_HOME", str(models / "huggingface"))
    try:
        # 公司或學校網路常會用自己的憑證攔截 HTTPS；改用 Windows 憑證庫
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
    from manga_translator.utils.inference import ModelWrapper

    ModelWrapper._MODEL_DIR = str(models)
    _bootstrap.done = True


def pick_device(preference: str = "auto") -> str:
    import torch

    if preference == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if preference == "cuda" and not torch.cuda.is_available():
        log.warning("找不到可用的 NVIDIA 顯卡，改用 CPU 模式（每頁會慢上好幾倍）")
        return "cpu"
    return preference


class Engine:
    def __init__(self, settings: EngineSettings | None = None):
        self.settings = settings or EngineSettings()
        _bootstrap()
        self.device = pick_device(self.settings.device)
        if self.settings.inpainting_size is None:
            vram = gpu_memory_gb() if self.device == "cuda" else None
            self.settings.inpainting_size = auto_inpainting_size(self.device, vram)
            log.info("擦字尺寸 %d（顯示卡記憶體 %s GB）", self.settings.inpainting_size, f"{vram:.1f}" if vram else "—")

    # ── 模型 ───────────────────────────────────────────────
    async def prepare(self, source: SourceLanguage) -> None:
        """下載並載入需要的模型（首次執行會比較久）。"""
        from manga_translator.config import Detector, Inpainter, Ocr
        from manga_translator.detection import prepare as prepare_detection
        from manga_translator.inpainting import prepare as prepare_inpainting
        from manga_translator.ocr import prepare as prepare_ocr

        await prepare_detection(Detector(self.settings.detector))
        await prepare_ocr(Ocr(source.ocr), self.device)
        await prepare_inpainting(Inpainter(self.settings.inpainter), self.device)

    # ── OCR：截圖 → 對話框 ────────────────────────────────
    async def recognize(self, image: np.ndarray, source: SourceLanguage) -> tuple[list[Region], np.ndarray]:
        """回傳依閱讀順序排好的對話框，以及偵測器輸出的原始文字遮罩。"""
        from manga_translator.config import Detector, Ocr, OcrConfig
        from manga_translator.detection import dispatch as detect
        from manga_translator.ocr import dispatch as ocr
        from manga_translator.textline_merge import dispatch as merge
        from manga_translator.utils import is_valuable_text
        from manga_translator.utils.sort import sort_regions

        s = self.settings
        textlines, mask_raw, _ = await detect(
            Detector(s.detector), image, s.detection_size, s.text_threshold, s.box_threshold, s.unclip_ratio,
            False, False, False, False, self.device, False,
        )
        if not textlines:
            return [], _empty_mask(image)
        textlines = await ocr(Ocr(source.ocr), image, textlines, OcrConfig(ocr=Ocr(source.ocr)), self.device, False)
        textlines = [t for t in textlines if t.text.strip()]
        if not textlines:
            return [], mask_raw
        blocks = await merge(textlines, image.shape[1], image.shape[0], verbose=False)
        blocks = [b for b in blocks if b.text.strip() and is_valuable_text(b.text.strip())]
        blocks = sort_regions(blocks, right_to_left=source.reading_rtl, img=image)
        return [_to_region(i, b) for i, b in enumerate(blocks)], mask_raw

    # ── 嵌字：對話框（含譯文）→ 譯圖 ──────────────────────
    async def inpaint(self, image: np.ndarray, regions: list[Region], mask_raw: np.ndarray) -> np.ndarray:
        from manga_translator.config import Inpainter, InpainterConfig, InpaintPrecision
        from manga_translator.inpainting import dispatch as inpaint
        from manga_translator.mask_refinement import dispatch as refine

        if not regions:
            return image.copy()
        blocks = [_to_textblock(r, None) for r in regions]
        mask = await refine(blocks, image, mask_raw, "fit_text", self.settings.mask_dilation_offset, 0, False, 3)
        cfg = InpainterConfig(
            inpainter=Inpainter(self.settings.inpainter),
            inpainting_size=self.settings.inpainting_size,
            inpainting_precision=InpaintPrecision.bf16 if _bf16_ok(self.device) else InpaintPrecision.fp32,
        )
        return await inpaint(cfg.inpainter, image, mask, cfg, self.settings.inpainting_size, self.device, False)

    async def typeset(self, inpainted: np.ndarray, regions: list[Region], target: TargetLanguage) -> np.ndarray:
        from manga_translator.rendering import dispatch as render
        from manga_translator.rendering import text_render

        blocks = [_to_textblock(r, target) for r in regions if r.translation]
        if not blocks:
            return inpainted.copy()
        main, fallbacks = fonts.ensure_for_target(target)
        # 上游預設的備援字型不是可再散布的字型，這裡換成 Noto
        text_render.FALLBACK_FONTS = [str(p) for p in fallbacks]
        text_render.get_char_glyph.cache_clear()
        if target.line_break == "cjk":
            text_render.set_font(str(main))
            _fix_vertical_forms(text_render, main)
            for b in blocks:
                _avoid_orphan_punctuation(b, text_render)
        return await render(inpainted.copy(), blocks, str(main), None, 0, -1,
                            target.line_break == "space", None, None)


# 直書時上游把部分標點換成直書字形，其中有些 Noto 子集字型沒有，會變成方框
_VERTICAL_REPLACEMENTS = {"⋮": "︙", "≀": "︴"}


def _fix_vertical_forms(text_render, font: Path) -> None:
    face = text_render.get_cached_font(str(font))
    table = text_render.CJK_H2V
    for src, dst in list(table.items()):
        if face.get_char_index(dst):
            continue
        alt = _VERTICAL_REPLACEMENTS.get(dst)
        if alt and face.get_char_index(alt):
            table[src] = alt
        else:
            del table[src]  # 找不到直書字形時保留原字
    text_render.get_char_glyph.cache_clear()


# 中日韓禁則：這些標點不能出現在一行（一欄）的開頭
NO_LINE_START = set("、。，．,.!！?？…‥:：;；」』）)】〉》〕］]ーｰ～〜・")


def _avoid_orphan_punctuation(block, text_render, min_scale: float = 0.75) -> None:
    """換行後若有一欄（行）以句尾標點開頭，稍微縮小字級讓標點跟上一個字放在一起。"""
    original = block.font_size
    width, height = block.unrotated_size
    while block.font_size > original * min_scale:
        if block.vertical:
            lines, _ = text_render.calc_vertical(block.font_size, block.translation, max_height=height)
        else:
            lines, _ = text_render.calc_horizontal(block.font_size, block.translation, max_width=width,
                                                   max_height=height, language=block.target_lang)
        if not any(line and line.strip()[:1] in NO_LINE_START for line in lines[1:]):
            return
        block.font_size = max(1, int(block.font_size * 0.94))
    block.font_size = original


# ── Region ⇄ TextBlock ───────────────────────────────────────

def _to_region(index: int, block) -> Region:
    return Region(
        id=index,
        text=block.text.strip(),
        lines=np.asarray(block.lines).astype(int).tolist(),
        texts=list(block.texts),
        direction="v" if block.vertical else "h",
        font_size=int(block.font_size),
        angle=float(block.angle),
        fg=[int(c) for c in np.asarray(block.fg_colors).ravel()[:3]],
        bg=[int(c) for c in np.asarray(block.bg_colors).ravel()[:3]],
        prob=float(block.prob),
    )


def _to_textblock(region: Region, target: TargetLanguage | None):
    from manga_translator.utils import TextBlock

    if target is None:
        direction = region.direction
    elif region.render_direction in ("h", "v"):
        direction = region.render_direction
    elif target.direction == "h":
        direction = "h"
    else:
        direction = region.direction
    block = TextBlock(
        lines=np.asarray(region.lines, dtype=np.int32),
        texts=region.texts or [region.text],
        font_size=region.font_size,
        angle=region.angle,
        translation=region.translation or "",
        fg_color=np.asarray(region.fg, dtype=np.float64),
        bg_color=np.asarray(region.bg, dtype=np.float64),
        direction=direction,
        target_lang=target.mit_code if target else "",
        prob=region.prob,
    )
    block.text = region.text
    block.text_raw = region.text
    return block


def _empty_mask(image: np.ndarray) -> np.ndarray:
    return np.zeros(image.shape[:2], dtype=np.uint8)


def _bf16_ok(device: str) -> bool:
    import torch

    return device == "cuda" and torch.cuda.is_bf16_supported(including_emulation=False)


# ── 圖片工具 ─────────────────────────────────────────────────

def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.array(im.convert("RGB"))


def save_rgb(array: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(path)


def regions_fingerprint(image_path: Path, regions: list[Region]) -> str:
    """擦字結果只跟原圖與對話框位置有關，跟譯文無關；位置沒變就沿用快取。"""
    h = hashlib.sha1()
    h.update(Path(image_path).read_bytes())
    h.update(json.dumps([r.lines for r in regions]).encode())
    return h.hexdigest()[:16]


def run(coro):
    """在同步程式（CLI）裡執行非同步的引擎呼叫。"""
    return asyncio.run(coro)
