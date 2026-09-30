"""實際跑 manga-image-translator 與 Claude Code 的整合測試。

預設不執行（見 pyproject 的 addopts）。手動執行：
    pytest -m gpu                 只測偵測、OCR、擦字與嵌字（首次會下載模型）
    pytest -m "gpu and claude"    再加上實際呼叫 claude -p 翻譯（消耗訂閱額度）
"""

import asyncio
import difflib
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "ja-page-01.png"
EXPECTED = json.loads(FIXTURE.with_name("ja-page-01.expected.json").read_text(encoding="utf-8"))["lines"]


@pytest.fixture(scope="module")
def engine():
    from app.engine import Engine
    from app.languages import get_source

    e = Engine()
    asyncio.run(e.prepare(get_source("ja")))
    return e


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


@pytest.mark.gpu
def test_ocr_reads_original_test_page(engine):
    from app.engine import load_rgb
    from app.languages import get_source

    regions, mask = asyncio.run(engine.recognize(load_rgb(FIXTURE), get_source("ja")))
    texts = [r.text for r in regions]
    matched = [max(texts, key=lambda t: _similarity(t, exp)) for exp in EXPECTED]
    scores = [_similarity(m, e) for m, e in zip(matched, EXPECTED)]
    assert sum(s >= 0.8 for s in scores) >= len(EXPECTED) - 1, list(zip(EXPECTED, texts))
    # 閱讀順序：由右至左、由上而下
    order = [texts.index(m) for m, s in zip(matched, scores) if s >= 0.8]
    assert order == sorted(order), texts
    assert mask.any()


@pytest.mark.gpu
def test_render_with_given_translations(engine, tmp_path):
    from app.engine import load_rgb
    from app.languages import get_source, get_target
    from app.page import Page
    from app.pipeline import render_page

    image = tmp_path / "001.png"
    image.write_bytes(FIXTURE.read_bytes())
    regions, _ = asyncio.run(engine.recognize(load_rgb(image), get_source("ja")))
    for r in regions:
        r.translation = "測試譯文"
    page = Page(image.name, 1200, 1700, "ja", "zh-TW", "mocr", regions)
    out = asyncio.run(render_page(engine, image, page, get_target("zh-TW")))
    assert out.is_file()
    assert (load_rgb(out) != load_rgb(image)).any()


@pytest.mark.gpu
@pytest.mark.claude
def test_full_translation(engine, tmp_path, monkeypatch):
    from app.pipeline import translate_image
    from app.translate import ClaudeCodeTranslator

    monkeypatch.setenv("YOMITOKI_APP_HOME", str(tmp_path / "app"))
    image = tmp_path / "page.png"
    image.write_bytes(FIXTURE.read_bytes())
    report = asyncio.run(translate_image(engine, ClaudeCodeTranslator(), image))
    assert report.output.is_file()
    assert report.page.is_translated, report.warnings
