import io
import json
from urllib.parse import unquote

import pytest
from PIL import Image

from app.series import Series
from tests.conftest import FakeEngine, FakeTranslator

H = {"X-Yomitoki-Client": "test"}


def png_bytes(size=(400, 300)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client(home, monkeypatch):
    """假引擎、假翻譯器：不需要顯卡，也不呼叫真的 claude。"""
    from fastapi.testclient import TestClient

    import app.server as server

    fake = FakeTranslator()
    monkeypatch.setattr(server, "ClaudeCodeTranslator", lambda model=None: fake)
    with TestClient(server.create_app(engine=FakeEngine(), ui_dist=None)) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "device": "cpu", "claude_code": True}


def test_translate_png_roundtrip(client):
    r = client.post("/translate", content=png_bytes(), headers={**H, "content-type": "image/png"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size == (400, 300)
    assert r.headers["x-yomitoki-regions"] == "2"
    assert json.loads(unquote(r.headers["x-yomitoki-warnings"])) == []

    r = client.post("/translate", files={"file": ("a.png", png_bytes(), "image/png")}, headers=H)
    assert r.status_code == 200


def test_translate_saves_into_episode(client):
    s = Series.create("作品")
    for _ in range(2):
        r = client.post("/translate", params={"series": "作品", "episode": "1"}, content=png_bytes(), headers=H)
        assert r.status_code == 200
    ep = s.episode_dir(1)
    assert sorted(p.name for p in ep.glob("*.png")) == ["001.png", "002.png"]
    assert (ep / "001.json").is_file() and (ep / "zh-TW" / "002.png").is_file()


def test_rejects_bad_input(client):
    assert client.post("/translate", content=b"", headers=H).status_code == 400
    assert client.post("/translate", content=b"not an image", headers=H).status_code == 415
    assert client.post("/translate", params={"series": "沒有這部"}, content=png_bytes(), headers=H).status_code == 400


def test_requires_client_header_for_writes(client):
    # 別的網站用表單或 fetch 送來的請求沒有自訂標頭
    assert client.post("/translate", content=png_bytes()).status_code == 403
    assert client.post("/api/series", json={"name": "x"}).status_code == 403
    assert client.get("/api/series").status_code == 200


def test_rejects_foreign_host(client):
    # DNS rebinding：網域指到 127.0.0.1，但 Host 是別人的網域
    r = client.get("/api/series", headers={"host": "evil.example.com"})
    assert r.status_code == 403
    assert client.get("/api/series", headers={"host": "127.0.0.1:8765"}).status_code == 200
