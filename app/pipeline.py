"""把引擎、翻譯與作品記憶串起來：單頁翻譯、整話 OCR / 翻譯 / 嵌字。

整話模式的檔案配置（每一頁）：
    ep001/001.png                    截圖
    ep001/001.json                   OCR 結果與譯文（Page）
    ep001/.cache/001.mask.png        偵測器輸出的文字遮罩
    ep001/.cache/001.<指紋>.png      擦字結果（對話框位置沒變就沿用）
    ep001/zh-TW/001.png              譯圖
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from . import paths
from .engine import Engine, load_rgb, regions_fingerprint, save_rgb
from .languages import SourceLanguage, TargetLanguage, get_source, get_target
from .page import Page
from .series import Glossary, Series
from .translate import ClaudeCodeTranslator, PageInput, SeriesMemory, TranslationResult

log = logging.getLogger("yomitoki.pipeline")

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
# 一次送給 Claude Code 的對話框數量上限；整話太長時分批，前面的譯文當作上下文
MAX_REGIONS_PER_CALL = 120

Progress = Callable[[str], None]


def _noop(_: str) -> None:
    pass


# ── 路徑 ─────────────────────────────────────────────────────

def page_json(image: Path) -> Path:
    return image.with_suffix(".json")


def mask_cache(image: Path) -> Path:
    return image.parent / ".cache" / f"{image.stem}.mask.png"


def inpaint_cache(image: Path, fingerprint: str) -> Path:
    return image.parent / ".cache" / f"{image.stem}.{fingerprint}.png"


def output_image(image: Path, target: TargetLanguage) -> Path:
    return image.parent / target.code / f"{image.stem}.png"


def episode_images(ep_dir: Path) -> list[Path]:
    return sorted(p for p in ep_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def work_dir_for(image: Path) -> Path:
    """不屬於任何作品的單張截圖：工作檔放在 %LOCALAPPDATA%\\Yomitoki\\work\\<雜湊>\\。"""
    digest = hashlib.sha1(image.read_bytes()).hexdigest()[:16]
    return paths.app_home() / "work" / digest


# ── 單頁 ─────────────────────────────────────────────────────

async def ocr_page(engine: Engine, image: Path, source: SourceLanguage, target: TargetLanguage) -> Page:
    rgb = load_rgb(image)
    regions, mask_raw = await engine.recognize(rgb, source)
    save_rgb(mask_raw, mask_cache(image))
    page = Page(
        image=image.name, width=rgb.shape[1], height=rgb.shape[0],
        source_lang=source.code, target_lang=target.code, ocr_engine=source.ocr, regions=regions,
    )
    page.save(page_json(image))
    return page


async def render_page(engine: Engine, image: Path, page: Page, target: TargetLanguage,
                      out: Path | None = None) -> Path:
    rgb = load_rgb(image)
    # 沒有譯文的對話框（例如無法翻譯的效果字）保留原文，不擦掉
    erase = [r for r in page.regions if r.translation]
    fp = regions_fingerprint(image, erase)
    cached = inpaint_cache(image, fp)
    if cached.is_file():
        inpainted = load_rgb(cached)
    else:
        mask_file = mask_cache(image)
        if mask_file.is_file():
            mask_raw = load_rgb(mask_file)[:, :, 0]
        else:
            _, mask_raw = await engine.recognize(rgb, get_source(page.source_lang))
        inpainted = await engine.inpaint(rgb, erase, mask_raw)
        for old in cached.parent.glob(f"{image.stem}.*.png"):
            if old.name != mask_file.name:
                old.unlink()
        save_rgb(inpainted, cached)
    rendered = await engine.typeset(inpainted, page.regions, target)
    out = out or output_image(image, target)
    save_rgb(rendered, out)
    return out


def apply_translations(items: Sequence[tuple[Path, PageInput]], result: TranslationResult,
                       glossary: Glossary | None, episode_label: str = "") -> int:
    """把譯文寫回每頁的 JSON，新名詞以「待確認」加入詞彙表。回傳新增的名詞數。"""
    for json_path, item in items:
        for r in item.page.regions:
            if (item.key, r.id) in result.translations:
                r.translation = result.translations[(item.key, r.id)]
        item.page.translated_by = "claude-code"
        item.page.save(json_path)
    added = 0
    if glossary is not None:
        first_seen = {}
        for _, item in items:
            for r in item.page.regions:
                for t in result.new_terms:
                    if t["source"] in r.text and t["source"] not in first_seen:
                        first_seen[t["source"]] = f"{episode_label}/{item.key}".strip("/")
        for t in result.new_terms:
            added += glossary.add_pending(t["source"], t["target"], t.get("category", "other"),
                                          t.get("note", ""), first_seen.get(t["source"], episode_label))
        glossary.save()
    return added


@dataclass
class PageReport:
    output: Path
    page: Page
    warnings: list[str] = field(default_factory=list)
    new_terms: int = 0
    seconds: dict[str, float] = field(default_factory=dict)


async def translate_image(engine: Engine, translator: ClaudeCodeTranslator, image: Path, *,
                          series: Series | None = None, source: str | None = None, target: str | None = None,
                          out: Path | None = None, progress: Progress = _noop) -> PageReport:
    """一張截圖從頭到尾：OCR → Claude Code 翻譯 → 擦字嵌字。"""
    src = get_source(source or (series.settings.source_lang if series else "ja"))
    tgt = get_target(target or (series.settings.target_lang if series else "zh-TW"))
    image = Path(image).resolve()

    # 不在作品資料夾裡的截圖，先複製到工作資料夾，避免在使用者的資料夾裡留下工作檔
    work_image = image
    if series is None or series.root not in image.parents:
        wd = work_dir_for(image)
        wd.mkdir(parents=True, exist_ok=True)
        work_image = wd / f"page{image.suffix.lower()}"
        if not work_image.exists():
            work_image.write_bytes(image.read_bytes())

    t = {}
    t0 = time.perf_counter()
    progress("辨識文字")
    page = await ocr_page(engine, work_image, src, tgt)
    t["ocr"] = time.perf_counter() - t0

    warnings: list[str] = []
    added = 0
    if page.regions:
        progress(f"翻譯 {len(page.regions)} 個對話框")
        t0 = time.perf_counter()
        memory = _memory(series, tgt)
        item = PageInput(work_image.stem, page)
        result = await asyncio.to_thread(translator.translate, [item], src, tgt, memory)
        added = apply_translations([(page_json(work_image), item)], result, memory.glossary)
        warnings = result.warnings
        t["translate"] = time.perf_counter() - t0
    else:
        warnings.append("這張圖裡沒有偵測到文字")

    progress("擦字與嵌字")
    t0 = time.perf_counter()
    out = Path(out) if out else image.with_name(f"{image.stem}.{tgt.code}.png")
    await render_page(engine, work_image, page, tgt, out)
    t["render"] = time.perf_counter() - t0
    return PageReport(out, page, warnings, added, t)


# ── 整話 ─────────────────────────────────────────────────────

async def ocr_episode(engine: Engine, series: Series, episode: str, *, force: bool = False,
                      progress: Progress = _noop) -> list[Path]:
    src, tgt = get_source(series.settings.source_lang), get_target(series.settings.target_lang)
    ep = series.episode_dir(episode)
    images = episode_images(ep)
    if not images:
        raise FileNotFoundError(f"{ep} 裡沒有截圖")
    done = []
    for i, image in enumerate(images, 1):
        if page_json(image).is_file() and not force:
            progress(f"[{i}/{len(images)}] {image.name} 已辨識過，略過")
            continue
        t0 = time.perf_counter()
        page = await ocr_page(engine, image, src, tgt)
        progress(f"[{i}/{len(images)}] {image.name}：{len(page.regions)} 個對話框（{time.perf_counter() - t0:.1f} 秒）")
        done.append(image)
    return done


def translate_episode(translator: ClaudeCodeTranslator, series: Series, episode: str, *, force: bool = False,
                      progress: Progress = _noop) -> tuple[list[str], int]:
    """用 claude -p 翻譯整話；太長時分批，前面的譯文當作後面的上下文。回傳（警告, 新名詞數）。"""
    src, tgt = get_source(series.settings.source_lang), get_target(series.settings.target_lang)
    ep = series.episode_dir(episode)
    pages: list[tuple[Path, PageInput]] = []
    for image in episode_images(ep):
        jp = page_json(image)
        if not jp.is_file():
            raise FileNotFoundError(f"{image.name} 還沒辨識文字，請先執行 yomitoki episode ocr")
        pages.append((jp, PageInput(image.stem, Page.load(jp))))

    glossary = series.glossary()
    memory = SeriesMemory(glossary=glossary, rules=series.rules(), summary=series.summary())
    todo = [(jp, p) for jp, p in pages if force or not p.page.is_translated]
    todo_ids = {id(p) for _, p in todo}
    for _, p in pages:
        if id(p) not in todo_ids:
            memory.previous += [(r.text, r.translation) for r in p.page.regions if r.translation]

    warnings: list[str] = []
    added = 0
    for batch in _batches(todo):
        keys = ", ".join(p.key for _, p in batch)
        progress(f"翻譯 {keys}（{sum(len(p.page.regions) for _, p in batch)} 個對話框）")
        result = translator.translate([p for _, p in batch], src, tgt, memory)
        added += apply_translations(batch, result, glossary, ep.name)
        warnings += result.warnings
        memory.previous += [(r.text, r.translation) for _, p in batch for r in p.page.regions if r.translation]
    return warnings, added


async def render_episode(engine: Engine, series: Series, episode: str, *, progress: Progress = _noop) -> list[Path]:
    tgt = get_target(series.settings.target_lang)
    ep = series.episode_dir(episode)
    outputs = []
    images = episode_images(ep)
    for i, image in enumerate(images, 1):
        jp = page_json(image)
        if not jp.is_file():
            progress(f"[{i}/{len(images)}] {image.name} 還沒辨識，略過")
            continue
        page = Page.load(jp)
        if page.regions and not page.is_translated:
            progress(f"[{i}/{len(images)}] {image.name} 還有對話框沒有譯文")
        t0 = time.perf_counter()
        outputs.append(await render_page(engine, image, page, tgt))
        progress(f"[{i}/{len(images)}] {image.name} 完成（{time.perf_counter() - t0:.1f} 秒）")
    return outputs


def _batches(items: list[tuple[Path, PageInput]]) -> list[list[tuple[Path, PageInput]]]:
    batches, current, count = [], [], 0
    for item in items:
        n = len(item[1].page.regions)
        if current and count + n > MAX_REGIONS_PER_CALL:
            batches.append(current)
            current, count = [], 0
        current.append(item)
        count += n
    if current:
        batches.append(current)
    return batches


def _memory(series: Series | None, target: TargetLanguage) -> SeriesMemory:
    if series is None:
        return SeriesMemory()
    return SeriesMemory(glossary=series.glossary(target.code), rules=series.rules(), summary=series.summary())

