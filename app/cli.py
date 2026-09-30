"""yomitoki 命令列工具。

    yomitoki setup                              下載模型與字型，檢查 Claude Code
    yomitoki translate 截圖.png [-o 譯圖.png]    單張截圖：OCR → 翻譯 → 嵌字
    yomitoki series new <作品名>                 建立作品資料夾
    yomitoki episode ocr|translate|render|run <作品名> <話數>
    yomitoki glossary list|set|confirm|remove <作品名> …
    yomitoki serve                              啟動本機 API（只綁 127.0.0.1）
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .languages import SOURCES, TARGETS, get_source, get_target
from .series import Series


def _print(msg: str) -> None:
    print(msg, flush=True)


def _engine(args):
    from .engine import Engine, EngineSettings

    _print("載入模型…（第一次會下載，需要幾分鐘）")
    return Engine(EngineSettings(device=args.device))


def _translator(args):
    from .translate import ClaudeCodeTranslator

    return ClaudeCodeTranslator(model=args.model)


# ── 指令 ─────────────────────────────────────────────────────

def cmd_setup(args) -> int:
    from . import fonts, paths
    from .engine import Engine, EngineSettings, run
    from .translate import ClaudeCodeTranslator

    src, tgt = get_source(args.source), get_target(args.target)
    _print(f"模型資料夾：{paths.models_dir()}")
    engine = Engine(EngineSettings(device=args.device))
    _print(f"運算裝置：{engine.device}")
    run(engine.prepare(src))
    main, fallbacks = fonts.ensure_for_target(tgt)
    _print(f"字型：{main.name}（備援 {', '.join(p.name for p in fallbacks)}）")
    exe = ClaudeCodeTranslator().executable
    _print(f"Claude Code：{exe or '找不到，請先安裝'}")
    return 0 if exe else 1


def cmd_translate(args) -> int:
    from .engine import run
    from .pipeline import translate_image

    series = Series.open(args.series) if args.series else None
    engine, translator = _engine(args), _translator(args)
    report = run(translate_image(engine, translator, Path(args.image), series=series, source=args.source,
                                 target=args.target, out=args.output, progress=lambda m: _print(f"・{m}")))
    _print_report(report)
    return 0


def _print_report(report) -> None:
    for r in report.page.regions:
        _print(f"  #{r.id} {r.text}\n     → {r.translation or '（無譯文）'}")
    for w in report.warnings:
        _print(f"  ⚠ {w}")
    if report.new_terms:
        _print(f"  新增 {report.new_terms} 個待確認名詞（yomitoki glossary list 查看）")
    timing = "、".join(f"{k} {v:.1f} 秒" for k, v in report.seconds.items())
    _print(f"完成：{report.output}（{timing}）")


def cmd_series_new(args) -> int:
    s = Series.create(args.name, format=args.format, source_lang=args.source, target_lang=args.target)
    _print(f"已建立作品「{s.name}」：{s.root}")
    _print(f"把截圖放進 {s.episode_dir(1)}\\ 之後執行：yomitoki episode run \"{s.name}\" 1")
    return 0


def cmd_series_list(args) -> int:
    items = Series.list()
    if not items:
        _print(f"還沒有作品（{Series.series_root()}）")
    for s in items:
        g = s.glossary()
        _print(f"{s.name}  [{s.settings.source_lang}→{s.settings.target_lang}, {s.settings.format}]  "
               f"{len(s.episodes())} 話，詞彙 {len(g.confirmed)} 個已確定 / {len(g.pending)} 個待確認")
    return 0


def cmd_series_show(args) -> int:
    import json

    s = Series.open(args.name)
    info = {
        "name": s.name,
        "root": str(s.root),
        "settings": vars(s.settings),
        "glossary": str(s.glossary_path()),
        "rules": str(s.root / "rules.md"),
        "summary": str(s.root / "summary.md"),
        "episodes": {ep: str(s.root / ep) for ep in s.episodes()},
    }
    _print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_episode(args) -> int:
    from .engine import run
    from .pipeline import ocr_episode, render_episode, translate_episode

    series = Series.open(args.series)
    progress = lambda m: _print(f"・{m}")  # noqa: E731
    lower_priority()
    t0 = time.perf_counter()
    engine = _engine(args) if args.step in ("ocr", "render", "run") else None
    if args.step in ("ocr", "run"):
        run(ocr_episode(engine, series, args.episode, force=args.force, progress=progress))
    if args.step in ("translate", "run"):
        warnings, added = translate_episode(_translator(args), series, args.episode, force=args.force, progress=progress)
        for w in warnings:
            _print(f"  ⚠ {w}")
        if added:
            _print(f"  新增 {added} 個待確認名詞（yomitoki glossary list \"{series.name}\" --pending）")
    if args.step in ("render", "run"):
        outs = run(render_episode(engine, series, args.episode, progress=progress))
        if outs:
            _print(f"譯圖在 {outs[0].parent}")
    _print(f"完成（{time.perf_counter() - t0:.0f} 秒）")
    return 0


def cmd_glossary(args) -> int:
    series = Series.open(args.series)
    g = series.glossary()
    if args.action == "list":
        terms = g.pending if args.pending else g.terms
        if not terms:
            _print("詞彙表是空的" if not args.pending else "沒有待確認的名詞")
        for t in sorted(terms, key=lambda t: (t.status != "pending", t.category, t.source)):
            mark = "待確認" if t.status == "pending" else "已確定"
            extra = f"  ({t.first_seen})" if t.first_seen else ""
            _print(f"[{mark}] {t.source} → {t.target}  <{t.category}>{extra}")
        return 0
    if args.action == "set":
        g.set(args.source, args.target, category=args.category, note=args.note)
    elif args.action == "confirm":
        if args.target:
            g.set(args.source, args.target)
        else:
            g.confirm(args.source)
    elif args.action == "remove":
        g.remove(args.source)
    g.save()
    _print("詞彙表已更新。已翻好的頁面可以用 yomitoki episode translate --force 重新翻譯後再嵌字。")
    return 0


def lower_priority() -> None:
    """長時間在背景跑的指令降低 CPU 優先權：辨識文字那幾秒，前景的程式會先拿到 CPU。"""
    if sys.platform == "win32":
        import ctypes

        BELOW_NORMAL_PRIORITY_CLASS = 0x4000
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
    else:
        try:
            import os

            os.nice(5)
        except OSError:
            pass


def cmd_serve(args) -> int:
    import uvicorn

    from .server import create_app

    lower_priority()
    uvicorn.run(create_app(device=args.device, model=args.model), host="127.0.0.1", port=args.port, log_level="info")
    return 0


# ── 參數 ─────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yomitoki", description="Yomitoki（よみとき・讀解）漫畫截圖翻譯工具")
    p.add_argument("-v", "--verbose", action="store_true", help="顯示詳細記錄")
    sub = p.add_subparsers(dest="command", required=True)

    def engine_opts(sp):
        sp.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"], help="運算裝置（預設自動偵測顯卡）")

    def claude_opts(sp):
        sp.add_argument("--model", help="Claude Code 使用的模型（預設沿用 Claude Code 的設定）")

    def lang_opts(sp, default_source=None, default_target=None):
        sp.add_argument("--source", default=default_source, choices=sorted(SOURCES), help="來源語言")
        sp.add_argument("--target", default=default_target, choices=sorted(TARGETS), help="目標語言")

    sp = sub.add_parser("setup", help="下載模型與字型，檢查 Claude Code")
    lang_opts(sp, "ja", "zh-TW")
    engine_opts(sp)
    sp.set_defaults(func=cmd_setup)

    sp = sub.add_parser("translate", help="翻譯一張截圖")
    sp.add_argument("image", help="截圖檔（PNG / JPG / WebP）")
    sp.add_argument("-o", "--output", help="譯圖輸出路徑（預設：<原檔名>.<目標語言>.png）")
    sp.add_argument("--series", help="作品名：帶入該作品的詞彙表、規則與劇情摘要")
    lang_opts(sp)
    engine_opts(sp)
    claude_opts(sp)
    sp.set_defaults(func=cmd_translate)

    series = sub.add_parser("series", help="管理作品").add_subparsers(dest="action", required=True)
    sp = series.add_parser("new", help="建立作品")
    sp.add_argument("name")
    sp.add_argument("--format", default="page", choices=["page", "scroll"], help="頁漫或條漫")
    lang_opts(sp, "ja", "zh-TW")
    sp.set_defaults(func=cmd_series_new)
    sp = series.add_parser("list", help="列出作品")
    sp.set_defaults(func=cmd_series_list)
    sp = series.add_parser("show", help="以 JSON 顯示作品的資料夾與記憶檔位置")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_series_show)

    sp = sub.add_parser("episode", help="整話處理")
    sp.add_argument("step", choices=["ocr", "translate", "render", "run"],
                    help="ocr = 辨識文字；translate = 用 Claude Code 翻譯；render = 擦字嵌字；run = 三步都做")
    sp.add_argument("series")
    sp.add_argument("episode", help="話數，例如 1 或 12")
    sp.add_argument("--force", action="store_true", help="已完成的頁面也重做")
    engine_opts(sp)
    claude_opts(sp)
    sp.set_defaults(func=cmd_episode)

    sp = sub.add_parser("glossary", help="詞彙表")
    sp.add_argument("action", choices=["list", "set", "confirm", "remove"])
    sp.add_argument("series")
    sp.add_argument("source", nargs="?", help="原文")
    sp.add_argument("target", nargs="?", help="譯名")
    sp.add_argument("--category", choices=["character", "place", "technique", "item", "other"])
    sp.add_argument("--note")
    sp.add_argument("--pending", action="store_true", help="只列出待確認的名詞")
    sp.set_defaults(func=cmd_glossary)

    sp = sub.add_parser("serve", help="啟動本機 API")
    sp.add_argument("--port", type=int, default=8765)
    engine_opts(sp)
    claude_opts(sp)
    sp.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(name)s: %(message)s")
    if args.command == "glossary" and args.action != "list" and not args.source:
        build_parser().error("請指定原文")
    if args.command == "glossary" and args.action == "set" and not args.target:
        build_parser().error("請指定譯名")
    from .translate import TranslationError

    try:
        return args.func(args)
    except (FileNotFoundError, FileExistsError, ValueError, TranslationError) as e:
        _print(f"錯誤：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
