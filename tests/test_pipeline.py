import asyncio
import shutil

from PIL import Image

from app import pipeline as pl
from app.page import Page
from app.series import Series
from tests.conftest import FakeEngine, FakeTranslator


def run(coro):
    return asyncio.run(coro)


def test_translate_single_image(home, screenshot):
    engine, translator = FakeEngine(), FakeTranslator()
    report = run(pl.translate_image(engine, translator, screenshot))
    assert report.output == screenshot.with_name("shot.zh-TW.png")
    assert report.output.is_file()
    assert [r.translation for r in report.page.regions] == ["譯:おはよう！", "譯:今日もいい天気だね"]
    # 單張截圖的工作檔不會留在使用者的資料夾
    left = {p.name for p in screenshot.parent.iterdir() if p.is_file()}
    assert left == {"shot.png", "shot.zh-TW.png"}
    assert not (screenshot.parent / ".cache").exists()
    assert set(report.seconds) == {"ocr", "translate", "render"}


def test_episode_flow_and_rerender_uses_cache(home):
    s = Series.create("作品")
    ep = s.episode_dir(1)
    ep.mkdir()
    for i in (1, 2, 3):
        Image.new("RGB", (400, 300), (230, 230, 230)).save(ep / f"{i:03d}.png")

    engine = FakeEngine(texts=["タヌ吉だ", "森へ"])
    translator = FakeTranslator(new_terms=[{"source": "タヌ吉", "target": "狸吉", "category": "character"}])
    run(pl.ocr_episode(engine, s, "1"))
    assert sorted(p.name for p in ep.glob("*.json")) == ["001.json", "002.json", "003.json"]

    warnings, added = pl.translate_episode(translator, s, "1")
    assert added == 1
    term = s.glossary().get("タヌ吉")
    assert term.status == "pending" and term.first_seen == "ep001/001"
    assert all(Page.load(ep / f"00{i}.json").is_translated for i in (1, 2, 3))

    outs = run(pl.render_episode(engine, s, "1"))
    assert [o.relative_to(ep).as_posix() for o in outs] == ["zh-TW/001.png", "zh-TW/002.png", "zh-TW/003.png"]
    assert engine.calls["inpaint"] == 3

    # 改譯文後重新嵌字：OCR 與擦字都沿用快取
    page = Page.load(ep / "001.json")
    page.regions[0].translation = "改過的譯文"
    page.save(ep / "001.json")
    run(pl.render_episode(engine, s, "1"))
    assert engine.calls["inpaint"] == 3 and engine.calls["recognize"] == 3


def test_translate_episode_skips_done_pages_and_passes_context(home):
    s = Series.create("作品")
    ep = s.episode_dir(1)
    ep.mkdir()
    for i in (1, 2):
        Image.new("RGB", (100, 100)).save(ep / f"{i:03d}.png")
    engine, translator = FakeEngine(), FakeTranslator()
    run(pl.ocr_episode(engine, s, "1"))
    pl.translate_episode(translator, s, "1")
    assert len(translator.calls) == 1

    # 新增一頁：只翻新的那頁，前面的譯文當作上下文
    shutil.copy(ep / "002.png", ep / "003.png")
    run(pl.ocr_episode(engine, s, "1"))
    pl.translate_episode(translator, s, "1")
    last = translator.calls[-1]
    assert [p.key for p in last["pages"]] == ["003"]
    assert ("おはよう！", "譯:おはよう！") in last["memory"].previous


def test_batches_split_long_episodes():
    from tests.conftest import make_region
    from app.translate import PageInput

    items = [(None, PageInput(f"{i:03d}", Page("x", 1, 1, "ja", "zh-TW", "mocr",
                                                [make_region(j, "あ") for j in range(50)]))) for i in range(5)]
    sizes = [len(b) for b in pl._batches(items)]
    assert sizes == [2, 2, 1]
