"""語言外掛：來源與目標語言都是設定值，OCR、文字方向、斷行與字型依語言切換。

新增語言時只要在這裡登記一個 SourceLanguage / TargetLanguage，
翻譯流程本身不需要修改。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Literal

Direction = Literal["auto", "h", "v"]


@dataclass(frozen=True)
class FontSpec:
    """嵌字用字型。只收 OFL 等可再散布的字型，首次使用時下載。"""

    id: str
    filename: str
    url: str
    license: str = "OFL-1.1"


# Noto Sans CJK 子集字型，固定在 Sans2.004 版本
_NOTO = "https://github.com/notofonts/noto-cjk/raw/Sans2.004/Sans/SubsetOTF"
FONTS: dict[str, FontSpec] = {
    "noto-sans-tc": FontSpec("noto-sans-tc", "NotoSansTC-Medium.otf", f"{_NOTO}/TC/NotoSansTC-Medium.otf"),
    "noto-sans-jp": FontSpec("noto-sans-jp", "NotoSansJP-Medium.otf", f"{_NOTO}/JP/NotoSansJP-Medium.otf"),
    "noto-sans-kr": FontSpec("noto-sans-kr", "NotoSansKR-Medium.otf", f"{_NOTO}/KR/NotoSansKR-Medium.otf"),
}


@dataclass(frozen=True)
class SourceLanguage:
    code: str
    name: str
    ocr: str                     # manga-image-translator 的 OCR 代號
    reading_rtl: bool            # 分格閱讀順序是否由右至左
    status: str = "supported"    # supported | planned


@dataclass(frozen=True)
class TargetLanguage:
    code: str
    name: str
    mit_code: str                # manga-image-translator 的語言代號（決定斷行規則）
    font: str                    # FONTS 的 key
    fallback_fonts: tuple[str, ...]
    direction: Direction         # auto = 依原文對話框形狀決定直書或橫書；h = 一律橫書
    line_break: Literal["cjk", "space"]  # cjk = 任意字間可斷；space = 只在空格斷行
    prompt_name: str             # 給翻譯模型看的語言描述
    normalize: Callable[[str], str] | None = field(default=None, compare=False)
    status: str = "supported"


@lru_cache(maxsize=1)
def _s2twp():
    import opencc

    return opencc.OpenCC("s2twp")


def _to_taiwan_traditional(text: str) -> str:
    """OpenCC s2twp 當保險：把可能混入的簡體字或對岸用語轉成台灣繁中。"""
    return _s2twp().convert(text)


SOURCES: dict[str, SourceLanguage] = {
    "ja": SourceLanguage("ja", "日文", ocr="mocr", reading_rtl=True),
    # v0.2：韓文 OCR 與橫書處理
    "ko": SourceLanguage("ko", "韓文", ocr="48px", reading_rtl=False, status="planned"),
    # v0.3
    "en": SourceLanguage("en", "英文", ocr="48px", reading_rtl=False, status="planned"),
    "zh": SourceLanguage("zh", "中文", ocr="48px", reading_rtl=True, status="planned"),
}

TARGETS: dict[str, TargetLanguage] = {
    "zh-TW": TargetLanguage(
        "zh-TW", "繁體中文（台灣）", mit_code="CHT", font="noto-sans-tc",
        fallback_fonts=("noto-sans-jp", "noto-sans-kr"), direction="auto", line_break="cjk",
        prompt_name="台灣繁體中文（使用台灣慣用詞彙與標點，例如「」與……）",
        normalize=_to_taiwan_traditional,
    ),
    # v0.3
    "en": TargetLanguage(
        "en", "English", mit_code="ENG", font="noto-sans-jp", fallback_fonts=("noto-sans-tc",),
        direction="h", line_break="space", prompt_name="natural English", status="planned",
    ),
    "ja": TargetLanguage(
        "ja", "日本語", mit_code="JPN", font="noto-sans-jp", fallback_fonts=("noto-sans-tc",),
        direction="auto", line_break="cjk", prompt_name="自然な日本語", status="planned",
    ),
    "ko": TargetLanguage(
        "ko", "한국어", mit_code="KOR", font="noto-sans-kr", fallback_fonts=("noto-sans-tc",),
        direction="h", line_break="space", prompt_name="자연스러운 한국어", status="planned",
    ),
}


class UnsupportedLanguageError(ValueError):
    pass


def get_source(code: str, allow_planned: bool = False) -> SourceLanguage:
    lang = SOURCES.get(code)
    if lang is None or (lang.status != "supported" and not allow_planned):
        supported = ", ".join(k for k, v in SOURCES.items() if v.status == "supported")
        raise UnsupportedLanguageError(f"目前不支援來源語言 {code!r}（可用：{supported}）")
    return lang


def get_target(code: str, allow_planned: bool = False) -> TargetLanguage:
    lang = TARGETS.get(code)
    if lang is None or (lang.status != "supported" and not allow_planned):
        supported = ", ".join(k for k, v in TARGETS.items() if v.status == "supported")
        raise UnsupportedLanguageError(f"目前不支援目標語言 {code!r}（可用：{supported}）")
    return lang
