import io
import json
from urllib.parse import unquote

from PIL import Image

from app.series import Series
from tests.conftest import FakeEngine, FakeTranslator


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def patch_translator(monkeypatch):
    """換成假翻譯器，不呼叫真的 claude。"""
    import app.server as server

    fake = FakeTranslator()
    monkeypatch.setattr(server, "ClaudeCodeTranslator", lambda model=None: fake)
    return fake


def test_health(home, monkeypatch):
    from fastapi.testclient import TestClient

    from app.server import create_app

    patch_translator(monkeypatch)
    with TestClient(create_app(engine=FakeEngine())) as c:
        assert c.get("/health").json() == {"status": "ok", "device": "cpu", "claude_code": True}


def test_translate_png_roundtrip(home, monkeypatch):
    from fastapi.testclient import TestClient

    from app.server import create_app

    patch_translator(monkeypatch)
    with TestClient(create_app(engine=FakeEngine())) as c:
        r = c.post("/translate", content=png_bytes(), headers={"content-type": "image/png"})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "image/png"
        assert Image.open(io.BytesIO(r.content)).size == (400, 300)
        assert r.headers["x-yomitoki-regions"] == "2"
        assert json.loads(unquote(r.headers["x-yomitoki-warnings"])) == []

        r = c.post("/translate", files={"file": ("a.png", png_bytes(), "image/png")})
        assert r.status_code == 200


def test_translate_saves_into_episode(home, monkeypatch):
    from fastapi.testclient import TestClient

    from app.server import create_app

    patch_translator(monkeypatch)
    s = Series.create("作品")
    with TestClient(create_app(engine=FakeEngine())) as c:
        for _ in range(2):
            r = c.post("/translate", params={"series": "作品", "episode": "1"}, content=png_bytes())
            assert r.status_code == 200
    ep = s.episode_dir(1)
    assert sorted(p.name for p in ep.glob("*.png")) == ["001.png", "002.png"]
    assert (ep / "001.json").is_file() and (ep / "zh-TW" / "002.png").is_file()


def test_rejects_bad_input(home, monkeypatch):
    from fastapi.testclient import TestClient

    from app.server import create_app

    patch_translator(monkeypatch)
    with TestClient(create_app(engine=FakeEngine())) as c:
        assert c.post("/translate", content=b"").status_code == 400
        assert c.post("/translate", content=b"not an image").status_code == 415
        assert c.post("/translate", params={"series": "沒有這部"}, content=png_bytes()).status_code == 400
