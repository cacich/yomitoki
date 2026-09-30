"""每部作品一個資料夾，翻譯前讀入、翻譯後更新，讓同一個名字永遠只有一個譯名。

    series/<作品名>/
      series.json            格式（頁漫 / 條漫）、來源與目標語言
      glossary.<目標>.json   人名、地名、招式名 → 固定譯名（每種目標語言各一份）
      rules.md               語氣與稱謂規則：角色口癖、敬語處理、第一人稱
      summary.md             劇情摘要，每翻完一話更新
      ep001/                 001.png、001.json（OCR 與譯文）、<目標>/001.png（譯圖）

規則：
- 已確定（confirmed）的譯名只能由使用者修改，模型不得自行更動。
- 詞彙表沒有的專有名詞先用暫定譯名、標記 pending，使用者確認後才算數。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Literal

from . import paths
from .languages import get_source, get_target

Status = Literal["confirmed", "pending"]
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

RULES_TEMPLATE = """# 語氣與稱謂規則

<!-- 翻譯時會整份帶入。用條列寫下這部作品的規則，例如： -->
<!-- - 主角第一人稱「俺」翻成「我」，語氣粗魯但不罵髒話 -->
<!-- - 「〜さん」一律省略；「〜先輩」翻成「學長／學姊」 -->
"""

SUMMARY_TEMPLATE = """# 劇情摘要

<!-- 每翻完一話，在下面補一段。翻譯時會帶入，幫助模型理解前情。 -->
"""


@dataclass
class Term:
    source: str
    target: str
    category: str = "other"          # character | place | technique | item | other
    status: Status = "pending"
    note: str = ""
    first_seen: str = ""             # 例如 ep001/003


@dataclass
class Glossary:
    path: Path
    terms: list[Term] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Glossary":
        if not path.is_file():
            return cls(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(path, [Term(**t) for t in data.get("terms", [])])

    def save(self) -> None:
        data = {"terms": [asdict(t) for t in self.terms]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, source: str) -> Term | None:
        return next((t for t in self.terms if t.source == source), None)

    @property
    def confirmed(self) -> list[Term]:
        return [t for t in self.terms if t.status == "confirmed"]

    @property
    def pending(self) -> list[Term]:
        return [t for t in self.terms if t.status == "pending"]

    def relevant(self, texts: Iterable[str]) -> list[Term]:
        """翻譯時要帶入的詞：全部已確定的詞，加上這次原文裡出現的待確認詞。"""
        joined = "\n".join(texts)
        return [t for t in self.terms if t.status == "confirmed" or t.source in joined]

    def add_pending(self, source: str, target: str, category: str = "other", note: str = "", first_seen: str = "") -> bool:
        """模型提出的新名詞。已存在（不論狀態）就不動，回傳是否新增。"""
        source, target = source.strip(), target.strip()
        if not source or not target or self.get(source):
            return False
        self.terms.append(Term(source, target, category or "other", "pending", note, first_seen))
        return True

    def set(self, source: str, target: str, category: str | None = None, note: str | None = None) -> Term:
        """使用者設定譯名：直接視為已確定。"""
        term = self.get(source)
        if term is None:
            term = Term(source, target)
            self.terms.append(term)
        term.target = target
        term.status = "confirmed"
        if category is not None:
            term.category = category
        if note is not None:
            term.note = note
        return term

    def confirm(self, source: str) -> Term:
        term = self.get(source)
        if term is None:
            raise KeyError(source)
        term.status = "confirmed"
        return term

    def remove(self, source: str) -> None:
        self.terms = [t for t in self.terms if t.source != source]


def safe_name(name: str) -> str:
    cleaned = _INVALID.sub("_", name).strip().rstrip(".")
    if not cleaned:
        raise ValueError("作品名不能是空的")
    return cleaned


def episode_dirname(episode: str | int) -> str:
    s = str(episode).strip()
    if s.lower().startswith("ep"):
        s = s[2:]
    return f"ep{int(s):03d}" if s.isdigit() else f"ep{safe_name(s)}"


@dataclass
class SeriesSettings:
    name: str
    format: Literal["page", "scroll"] = "page"
    source_lang: str = "ja"
    target_lang: str = "zh-TW"
    created: str = field(default_factory=lambda: date.today().isoformat())


class Series:
    def __init__(self, root: Path):
        self.root = Path(root)
        data = json.loads((self.root / "series.json").read_text(encoding="utf-8"))
        self.settings = SeriesSettings(**data)

    # ── 建立與尋找 ─────────────────────────────────────────
    @staticmethod
    def series_root() -> Path:
        return paths.data_home() / "series"

    @classmethod
    def create(cls, name: str, *, format: str = "page", source_lang: str = "ja", target_lang: str = "zh-TW",
               root: Path | None = None) -> "Series":
        get_source(source_lang)
        get_target(target_lang)
        folder = (root or cls.series_root()) / safe_name(name)
        if (folder / "series.json").exists():
            raise FileExistsError(f"作品「{name}」已存在：{folder}")
        folder.mkdir(parents=True, exist_ok=True)
        settings = SeriesSettings(name=name, format=format, source_lang=source_lang, target_lang=target_lang)
        (folder / "series.json").write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "rules.md").write_text(RULES_TEMPLATE, encoding="utf-8")
        (folder / "summary.md").write_text(SUMMARY_TEMPLATE, encoding="utf-8")
        return cls(folder)

    @classmethod
    def open(cls, name_or_path: str | Path, root: Path | None = None) -> "Series":
        p = Path(name_or_path)
        if (p / "series.json").is_file():
            return cls(p)
        folder = (root or cls.series_root()) / safe_name(str(name_or_path))
        if not (folder / "series.json").is_file():
            raise FileNotFoundError(f"找不到作品「{name_or_path}」（{folder}）。先用 yomitoki series new 建立。")
        return cls(folder)

    @classmethod
    def list(cls, root: Path | None = None) -> list["Series"]:
        base = root or cls.series_root()
        if not base.is_dir():
            return []
        return [cls(p) for p in sorted(base.iterdir()) if (p / "series.json").is_file()]

    # ── 記憶檔 ─────────────────────────────────────────────
    @property
    def name(self) -> str:
        return self.settings.name

    def glossary_path(self, target_lang: str | None = None) -> Path:
        return self.root / f"glossary.{target_lang or self.settings.target_lang}.json"

    def glossary(self, target_lang: str | None = None) -> Glossary:
        return Glossary.load(self.glossary_path(target_lang))

    def rules(self) -> str:
        return _strip_comments((self.root / "rules.md").read_text(encoding="utf-8"))

    def summary(self) -> str:
        return _strip_comments((self.root / "summary.md").read_text(encoding="utf-8"))

    def append_summary(self, episode: str, text: str) -> None:
        path = self.root / "summary.md"
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\n## {episode_dirname(episode)}\n\n{text.strip()}\n")

    # ── 話數 ───────────────────────────────────────────────
    def episode_dir(self, episode: str | int) -> Path:
        return self.root / episode_dirname(episode)

    def episodes(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and p.name.startswith("ep"))


def _strip_comments(md: str) -> str:
    text = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("# ")]
    return "\n".join(lines).strip()
