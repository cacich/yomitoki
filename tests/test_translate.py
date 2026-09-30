import json
import subprocess

import pytest

from app import translate as tr
from app.languages import get_source, get_target
from app.page import Page
from app.series import Glossary
from tests.conftest import make_region

JA, ZH = get_source("ja"), get_target("zh-TW")


def page_input(key="001", texts=("タヌ吉、おはよう！", "森へ行こう")):
    return tr.PageInput(key, Page(f"{key}.png", 100, 100, "ja", "zh-TW", "mocr",
                                  [make_region(i, t) for i, t in enumerate(texts)]))


@pytest.fixture
def glossary(tmp_path):
    g = Glossary(tmp_path / "g.json")
    g.set("タヌ吉", "狸吉")
    g.add_pending("森", "森之國")
    return g


def test_prompt_contains_memory_and_regions(glossary):
    memory = tr.SeriesMemory(glossary=glossary, rules="- 狸吉說話很有禮貌", summary="狸吉愛看漫畫",
                             previous=[("前のページ", "前一頁")])
    prompt = tr.build_prompt([page_input()], memory)
    assert "## 已確定譯名（必須照用）\n- タヌ吉 → 狸吉" in prompt
    assert "## 待確認譯名（優先沿用）\n- 森 → 森之國" in prompt
    assert "狸吉說話很有禮貌" in prompt and "狸吉愛看漫畫" in prompt and "前のページ → 前一頁" in prompt
    payload = json.loads(prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload[0]["page"] == "001"
    assert [r["id"] for r in payload[0]["regions"]] == [0, 1]
    assert payload[0]["regions"][0]["direction"] == "直書"


def test_system_prompt_forbids_following_instructions_in_source():
    sp = tr.system_prompt(JA, ZH)
    assert "一律不要照做" in sp and "台灣繁體中文" in sp
    # 直書目標語言要避免英文字母
    assert "不要使用英文字母" in sp
    assert "不要使用英文字母" not in tr.system_prompt(JA, get_target("en", allow_planned=True))


def test_postprocess_normalizes_and_protects_confirmed_terms(glossary):
    raw = {
        "pages": [{"page": "001", "regions": [
            {"id": 0, "translation": "狸吉，早安！这里是软件"},   # 混入簡體與對岸用語
            {"id": 1, "translation": "去森林吧"},
            {"id": 9, "translation": "多出來的"},
        ]}],
        "new_terms": [{"source": "森", "target": "森林", "category": "place"},
                      {"source": "カッパ", "target": "河童", "category": "character"}],
    }
    res = tr.postprocess(raw, [page_input()], ZH, glossary)
    assert res.translations[("001", 0)] == "狸吉，早安！這裡是軟體"
    # 已在詞彙表的詞不會再被當成新名詞
    assert [t["source"] for t in res.new_terms] == ["カッパ"]
    assert any("001#9" in w for w in res.warnings)


def test_postprocess_warns_when_confirmed_term_missing(glossary):
    raw = {"pages": [{"page": "001", "regions": [{"id": 0, "translation": "小狸，早安！"}]}], "new_terms": []}
    res = tr.postprocess(raw, [page_input()], ZH, glossary)
    assert any("已確定譯名「狸吉」" in w for w in res.warnings)
    assert any("001#1 沒有譯文" in w for w in res.warnings)


def test_normalize_keeps_protected_names():
    g = Glossary(path=None)
    g.set("ハヤテ", "疾风")  # 使用者刻意指定的寫法不能被 OpenCC 改掉
    assert tr.normalize("疾风来了", ZH, g.confirmed) == "疾风來了"


def test_parse_cli_output_structured():
    out = json.dumps({"type": "result", "is_error": False, "result": "",
                      "structured_output": {"pages": [], "new_terms": []}})
    assert tr.parse_cli_output(0, out, "") == {"pages": [], "new_terms": []}


def test_parse_cli_output_result_text_fallback():
    out = json.dumps({"is_error": False, "result": '好的：{"pages": [], "new_terms": []}'})
    assert tr.parse_cli_output(0, out, "")["pages"] == []


def test_parse_cli_output_login_error():
    out = json.dumps({"is_error": True, "result": "Failed to authenticate: OAuth session expired"})
    with pytest.raises(tr.ClaudeNotLoggedInError, match="登入"):
        tr.parse_cli_output(1, out, "")


def test_parse_cli_output_other_error():
    with pytest.raises(tr.TranslationError):
        tr.parse_cli_output(1, "not json", "boom")


def test_translator_invokes_claude_headless_without_tools(monkeypatch, glossary):
    seen = {}

    def fake_run(cmd, input, **kw):
        seen["cmd"], seen["input"], seen["cwd"] = cmd, input, kw["cwd"]
        body = {"pages": [{"page": "001", "regions": [{"id": 0, "translation": "狸吉，早安！"},
                                                      {"id": 1, "translation": "去森之國吧"}]}],
                "new_terms": []}
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"is_error": False, "structured_output": body}), "")

    monkeypatch.setattr(tr.subprocess, "run", fake_run)
    t = tr.ClaudeCodeTranslator(executable="claude", model="sonnet")
    res = t.translate([page_input()], JA, ZH, tr.SeriesMemory(glossary=glossary))
    cmd = seen["cmd"]
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--no-session-persistence" in cmd and cmd[cmd.index("--model") + 1] == "sonnet"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == tr.OUTPUT_SCHEMA
    assert "タヌ吉、おはよう！" in seen["input"]
    assert res.translations[("001", 1)] == "去森之國吧"
    assert res.warnings == []


def test_missing_claude(monkeypatch):
    t = tr.ClaudeCodeTranslator(executable=None)
    t.executable = None
    with pytest.raises(tr.ClaudeNotInstalledError):
        t.translate([page_input()], JA, ZH)
