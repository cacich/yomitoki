"""共用的假引擎與假翻譯器：不需要顯卡、模型或 Claude Code 就能測整個流程。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.page import Region
from app.translate import TranslationResult


def make_region(i: int, text: str, x: int = 100) -> Region:
    return Region(
        id=i, text=text, lines=[[[x, 50], [x + 40, 50], [x + 40, 250], [x, 250]]], texts=[text],
        direction="v", font_size=36,
    )


class FakeEngine:
    device = "cpu"

    def __init__(self, texts=("おはよう！", "今日もいい天気だね")):
        self.texts = list(texts)
        self.calls = {"recognize": 0, "inpaint": 0, "typeset": 0}

    async def prepare(self, source):
        pass

    async def recognize(self, image, source):
        self.calls["recognize"] += 1
        regions = [make_region(i, t, 100 + 80 * i) for i, t in enumerate(self.texts)]
        return regions, np.zeros(image.shape[:2], dtype=np.uint8)

    async def inpaint(self, image, regions, mask_raw):
        self.calls["inpaint"] += 1
        return np.full_like(image, 255)

    async def typeset(self, inpainted, regions, target):
        self.calls["typeset"] += 1
        out = inpainted.copy()
        for r in regions:
            if r.translation:
                x1, y1, x2, y2 = r.bbox
                out[y1:y2, x1:x2] = 0
        return out


class FakeTranslator:
    executable = "claude"

    def __init__(self, new_terms=None):
        self.calls = []
        self.new_terms = new_terms or []

    def translate(self, pages, source, target, memory=None):
        self.calls.append({"pages": pages, "memory": memory})
        translations = {(p.key, r.id): f"譯:{r.text}" for p in pages for r in p.page.regions}
        return TranslationResult(translations, list(self.new_terms), [], {})


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("YOMITOKI_HOME", str(tmp_path / "docs"))
    monkeypatch.setenv("YOMITOKI_APP_HOME", str(tmp_path / "app"))
    return tmp_path


@pytest.fixture
def screenshot(tmp_path):
    p = tmp_path / "shot.png"
    Image.new("RGB", (400, 300), (240, 240, 240)).save(p)
    return p
