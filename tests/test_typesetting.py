"""嵌字前的中日韓禁則處理：不讓句尾標點單獨成一欄。用假的斷行函式測，不需要上游套件。"""

from types import SimpleNamespace

from app.engine import _avoid_orphan_punctuation


class FakeTextRender:
    """每欄可放的字數 = 欄高 // 字級。"""

    @staticmethod
    def calc_vertical(font_size, text, max_height):
        per = max(1, max_height // font_size)
        return [text[i : i + per] for i in range(0, len(text), per)], None

    @staticmethod
    def calc_horizontal(font_size, text, max_width, max_height, language):
        per = max(1, max_width // font_size)
        return [text[i : i + per] for i in range(0, len(text), per)], None


def block(text, font_size=40, height=280, vertical=True):
    return SimpleNamespace(translation=text, font_size=font_size, unrotated_size=(120, height),
                           vertical=vertical, target_lang="CHT")


def test_shrinks_until_punctuation_joins_previous_column():
    b = block("全部都看得懂了！")        # 字級 40、欄高 280 → 每欄 7 字，「！」會落單
    _avoid_orphan_punctuation(b, FakeTextRender)
    assert b.font_size < 40
    lines, _ = FakeTextRender.calc_vertical(b.font_size, b.translation, 280)
    assert all(line[0] != "！" for line in lines[1:])


def test_leaves_normal_breaks_alone():
    b = block("交給讀解吧！", height=160)  # 每欄 4 字：「交給讀解」「吧！」，第二欄不是以標點開頭
    _avoid_orphan_punctuation(b, FakeTextRender)
    assert b.font_size == 40


def test_gives_up_instead_of_shrinking_too_much():
    b = block("好" * 20 + "！", height=80)
    _avoid_orphan_punctuation(b, FakeTextRender)
    assert b.font_size == 40
