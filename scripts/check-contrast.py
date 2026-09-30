"""檢查 ui/src/styles/tokens.css 中文字與底色的對比是否通過 WCAG AA。

用法：python scripts/check-contrast.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS_CSS = ROOT / "ui" / "src" / "styles" / "tokens.css"

AA_TEXT = 4.5
AA_UI = 3.0  # 非文字元件（線條、焦點框）

# (前景變數, 背景變數, 最低對比, 說明)
PAIRS: list[tuple[str, str, float, str]] = [
    ("--text-primary", "--bg-page", AA_TEXT, "主要文字 / 頁面"),
    ("--text-primary", "--bg-card", AA_TEXT, "主要文字 / 卡片"),
    ("--text-secondary", "--bg-page", AA_TEXT, "次要文字 / 頁面"),
    ("--text-secondary", "--bg-card", AA_TEXT, "次要文字 / 卡片"),
    ("--button-primary-text", "--button-primary-bg", AA_TEXT, "主要按鈕文字"),
    ("--text-on-tag", "--bg-tag-sage", AA_TEXT, "文字 / 鼠尾草綠標籤"),
    ("--text-on-tag", "--bg-tag-butter", AA_TEXT, "文字 / 奶油黃標籤"),
    ("--text-on-tag", "--bg-tag-rose", AA_TEXT, "文字 / 霧玫瑰標籤"),
    ("--line-sketch", "--bg-page", AA_UI, "手繪線條 / 頁面"),
    ("--line-sketch", "--bg-card", AA_UI, "手繪線條 / 卡片"),
    ("--focus-ring", "--bg-page", AA_UI, "焦點框 / 頁面"),
]

THEMES = {"light": r":root\s*\{", "night": r':root\[data-theme="night"\]\s*\{'}


def _block(css: str, selector_re: str) -> str:
    m = re.search(selector_re, css)
    if not m:
        raise ValueError(f"找不到選擇器 {selector_re}")
    depth, i = 1, m.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return css[m.end() : i - 1]


def _vars(block: str) -> dict[str, str]:
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    return {k: v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block)}


def load_themes(css: str | None = None) -> dict[str, dict[str, str]]:
    css = css if css is not None else TOKENS_CSS.read_text(encoding="utf-8")
    light = _vars(_block(css, THEMES["light"]))
    night = {**light, **_vars(_block(css, THEMES["night"]))}
    return {"light": light, "night": night}


def resolve(name: str, variables: dict[str, str]) -> str:
    value = variables[name]
    for _ in range(10):
        m = re.fullmatch(r"var\((--[\w-]+)\)", value)
        if not m:
            return value
        value = variables[m.group(1)]
    raise ValueError(f"{name} 的 var() 參照太深")


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check(css: str | None = None) -> list[dict]:
    results = []
    for theme, variables in load_themes(css).items():
        for fg, bg, minimum, label in PAIRS:
            fg_hex, bg_hex = resolve(fg, variables), resolve(bg, variables)
            ratio = contrast(fg_hex, bg_hex)
            results.append(
                {
                    "theme": theme,
                    "label": label,
                    "fg": fg_hex,
                    "bg": bg_hex,
                    "ratio": ratio,
                    "minimum": minimum,
                    "ok": ratio >= minimum,
                }
            )
    return results


def main() -> int:
    results = check()
    for r in results:
        mark = "OK " if r["ok"] else "FAIL"
        print(f"[{mark}] {r['theme']:<5} {r['label']:<18} {r['fg']} on {r['bg']}  {r['ratio']:.2f}:1 (≥ {r['minimum']})")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} 通過")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
