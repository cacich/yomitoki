import pytest

from app.page import Page
from app.series import Glossary, Series, episode_dirname, safe_name
from tests.conftest import make_region


def test_create_and_open(home):
    s = Series.create("テスト作品", source_lang="ja", target_lang="zh-TW")
    assert (s.root / "series.json").is_file()
    assert (s.root / "rules.md").is_file()
    assert Series.open("テスト作品").settings.target_lang == "zh-TW"
    assert [x.name for x in Series.list()] == ["テスト作品"]
    with pytest.raises(FileExistsError):
        Series.create("テスト作品")


def test_rejects_unsupported_language(home):
    with pytest.raises(ValueError):
        Series.create("x", source_lang="xx")
    with pytest.raises(ValueError):
        Series.create("y", source_lang="ko")  # v0.2 才支援


def test_open_missing(home):
    with pytest.raises(FileNotFoundError):
        Series.open("不存在")


def test_names():
    assert safe_name('a/b:c*?') == "a_b_c__"
    assert episode_dirname(1) == "ep001"
    assert episode_dirname("ep12") == "ep012"
    assert episode_dirname("12.5") == "ep12.5"


def test_glossary_rules(tmp_path):
    g = Glossary(tmp_path / "glossary.zh-TW.json")
    assert g.add_pending("タヌ吉", "狸吉", "character", first_seen="ep001/002")
    # 已存在的詞不會被模型覆蓋
    assert not g.add_pending("タヌ吉", "狸太郎")
    assert g.get("タヌ吉").target == "狸吉"
    g.confirm("タヌ吉")
    assert not g.add_pending("タヌ吉", "別的")
    assert g.get("タヌ吉").status == "confirmed"
    # 使用者設定的一律是已確定
    g.set("よみとき", "讀解")
    g.save()
    g2 = Glossary.load(g.path)
    assert {t.source for t in g2.confirmed} == {"タヌ吉", "よみとき"}
    g2.add_pending("森", "森林")
    rel = {t.source for t in g2.relevant(["森へ行こう"])}
    assert rel == {"タヌ吉", "よみとき", "森"}
    assert "森" not in {t.source for t in g2.relevant(["ほかの話"])}


def test_rules_and_summary_strip_template_comments(home):
    s = Series.create("作品")
    assert s.rules() == ""
    assert s.summary() == ""
    (s.root / "rules.md").write_text("# 語氣\n\n- 主角自稱「俺」翻成「我」\n", encoding="utf-8")
    s.append_summary(1, "狸貓開始讀漫畫。")
    assert s.rules() == "- 主角自稱「俺」翻成「我」"
    assert "## ep001" in s.summary() and "狸貓開始讀漫畫" in s.summary()


def test_glossary_per_target_language(home):
    s = Series.create("作品")
    g = s.glossary()
    g.set("タヌ吉", "狸吉")
    g.save()
    assert s.glossary("en").terms == []
    assert s.glossary_path().name == "glossary.zh-TW.json"


def test_page_roundtrip(tmp_path):
    page = Page("001.png", 800, 1200, "ja", "zh-TW", "mocr", [make_region(0, "おはよう")])
    p = tmp_path / "001.json"
    page.save(p)
    loaded = Page.load(p)
    assert loaded == page
    assert not loaded.is_translated
    loaded.regions[0].translation = "早安"
    assert loaded.is_translated
    assert loaded.regions[0].bbox == (100, 50, 140, 250)
