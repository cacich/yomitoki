"""每頁一個 JSON：原文、座標、閱讀順序，以及之後寫回的譯文。

檔案放在截圖旁邊，例如 ep001/001.png → ep001/001.json。
OCR 只跑一次；改詞彙表或重新翻譯後，只需要讀這個 JSON 重做嵌字。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class Region:
    id: int
    text: str                                   # 合併後的原文
    lines: list[list[list[int]]]                # 每一行文字框的四個角 [[x, y] × 4]
    texts: list[str]                            # 每一行各自的原文
    direction: str                              # 原文方向 h / v
    font_size: int
    angle: float = 0.0
    fg: list[int] = field(default_factory=lambda: [0, 0, 0])
    bg: list[int] = field(default_factory=lambda: [255, 255, 255])
    prob: float = 1.0
    translation: str | None = None              # 由翻譯步驟寫回
    render_direction: str | None = None         # 手動指定嵌字方向 h / v（None = 依語言規則）

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        xs = [p[0] for line in self.lines for p in line]
        ys = [p[1] for line in self.lines for p in line]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass
class Page:
    image: str                                  # 截圖檔名（相對於 JSON 所在資料夾）
    width: int
    height: int
    source_lang: str
    target_lang: str
    ocr_engine: str
    regions: list[Region]                       # 已依閱讀順序排列
    translated_by: str | None = None
    schema: int = SCHEMA_VERSION

    @property
    def is_translated(self) -> bool:
        return bool(self.regions) and all(r.translation for r in self.regions)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Page":
        if data.get("schema", 1) > SCHEMA_VERSION:
            raise ValueError(f"頁面 JSON 版本 {data['schema']} 比程式支援的 {SCHEMA_VERSION} 新")
        regions = [Region(**r) for r in data.get("regions", [])]
        fields = {k: v for k, v in data.items() if k != "regions"}
        return cls(regions=regions, **fields)

    def save(self, path: Path) -> None:
        path = Path(path)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Page":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
