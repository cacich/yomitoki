import io
import time

import pytest
from PIL import Image

from tests.conftest import FakeEngine, FakeTranslator

H = {"X-Yomitoki-Client": "test"}


def png(color=(220, 220, 220)):
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client(home, monkeypatch):
    from fastapi.testclient import TestClient

    import app.server as server

    fake = FakeTranslator(new_terms=[{"source": "おはよう", "target": "早安", "category": "other"}])
    monkeypatch.setattr(server, "ClaudeCodeTranslator", lambda model=None: fake)
    with TestClient(server.create_app(engine=FakeEngine(), ui_dist=None)) as c:
        yield c


def wait_job(client, job_id, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job 沒有結束")


def test_series_crud_and_listing(client):
    assert client.get("/api/series").json() == []
    r = client.post("/api/series", json={"name": "狸貓日記"}, headers=H)
    assert r.status_code == 201
    assert client.post("/api/series", json={"name": "狸貓日記"}, headers=H).status_code == 409
    assert client.post("/api/series", json={"name": "x", "source_lang": "ko"}, headers=H).status_code == 400
    items = client.get("/api/series").json()
    assert [i["name"] for i in items] == ["狸貓日記"]
    assert items[0]["cover"] is None and items[0]["episodes"] == 0
    assert client.get("/api/series/沒有這部").status_code == 404


def test_full_episode_flow(client):
    client.post("/api/series", json={"name": "作品"}, headers=H)
    ep = client.post("/api/series/作品/episodes", json={}, headers=H).json()
    assert ep["id"] == "ep001" and ep["status"] == "empty"

    files = [("files", ("p10.png", png(), "image/png")), ("files", ("p2.png", png((0, 0, 0)), "image/png"))]
    saved = client.post("/api/series/作品/episodes/ep001/pages", files=files, headers=H).json()["saved"]
    assert saved == ["001", "002"]  # 依檔名的自然順序：p2 在 p10 前面

    detail = client.get("/api/series/作品/episodes/ep001").json()
    assert [p["status"] for p in detail["pages_detail"]] == ["new", "new"]
    assert detail["pages_detail"][0]["translated"] is None

    job = client.post("/api/series/作品/episodes/ep001/run", json={}, headers=H).json()
    job = wait_job(client, job["id"])
    assert job["status"] == "done", job
    assert job["new_terms"] == 1

    detail = client.get("/api/series/作品/episodes/ep001").json()
    assert detail["status"] == "done"
    page = detail["pages_detail"][0]
    assert page["status"] == "done" and page["regions"] == 2
    img = client.get(page["translated"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    thumb = client.get(page["thumb"])
    assert thumb.status_code == 200 and Image.open(io.BytesIO(thumb.content)).width == 320

    shelf = client.get("/api/series").json()[0]
    assert shelf["done_pages"] == 2 and shelf["pending_terms"] == 1 and shelf["cover"]


def test_run_rejects_empty_episode_and_bad_upload(client):
    client.post("/api/series", json={"name": "作品"}, headers=H)
    client.post("/api/series/作品/episodes", json={}, headers=H)
    assert client.post("/api/series/作品/episodes/ep001/run", json={}, headers=H).status_code == 400
    bad = [("files", ("a.png", b"nope", "image/png"))]
    assert client.post("/api/series/作品/episodes/ep001/pages", files=bad, headers=H).status_code == 415
    assert client.get("/api/series/作品/episodes/ep001/pages/..%2F..%2Fsecret/image").status_code == 404


def test_glossary_and_notes(client):
    client.post("/api/series", json={"name": "作品"}, headers=H)
    g = client.post("/api/series/作品/glossary/set",
                    json={"source": "タヌ吉", "target": "狸吉", "category": "character"}, headers=H).json()
    assert g["terms"][0]["status"] == "confirmed"
    assert client.post("/api/series/作品/glossary/confirm", json={"source": "沒有"}, headers=H).status_code == 404
    g = client.post("/api/series/作品/glossary/remove", json={"source": "タヌ吉"}, headers=H).json()
    assert g["terms"] == []

    notes = client.get("/api/series/作品/notes").json()
    assert "語氣與稱謂規則" in notes["rules"]
    client.put("/api/series/作品/notes", json={"rules": "- 狸吉很有禮貌", "summary": notes["summary"]}, headers=H)
    assert client.get("/api/series/作品/notes").json()["rules"] == "- 狸吉很有禮貌"


def test_assets_replace_and_restore(client, home):
    items = client.get("/api/assets").json()
    welcome = next(a for a in items if a["id"] == "mascot-welcome")
    assert welcome["source"] == "default"
    assert client.get(welcome["url"]).headers["content-type"].startswith("image/svg+xml")

    buf = io.BytesIO()
    Image.new("RGBA", (1600, 1600), (0, 128, 0, 255)).save(buf, format="PNG")
    items = client.post("/api/assets/mascot-welcome", files={"file": ("mine.png", buf.getvalue(), "image/png")},
                        headers=H).json()
    welcome = next(a for a in items if a["id"] == "mascot-welcome")
    assert welcome["source"] == "custom" and welcome["pixel_size"] == [1600, 1600]
    assert (home / "docs" / "custom-assets" / "mascot-welcome.png").is_file()

    bad = client.post("/api/assets/mascot-welcome", files={"file": ("x.gif", b"GIF89a", "image/gif")}, headers=H)
    assert bad.status_code == 415
    items = client.delete("/api/assets/mascot-welcome", headers=H).json()
    assert next(a for a in items if a["id"] == "mascot-welcome")["source"] == "default"


def test_status_hides_account_details(client, monkeypatch):
    import subprocess

    import app.api as api

    def fake_run(cmd, **kw):
        out = '{"loggedIn": true, "subscriptionType": "pro", "email": "someone@example.com"}' if "auth" in cmd else "2.1.0 (Claude Code)"
        return subprocess.CompletedProcess(cmd, 0, out, "")

    monkeypatch.setattr(api.subprocess, "run", fake_run)
    # 單元測試不載入 torch（第一次 import 很慢）
    monkeypatch.setattr(api, "_gpu_status", lambda device: {"cuda": False, "name": None, "vram_gb": None, "device": device})
    s = client.get("/api/status").json()
    assert s["claude"] == {"installed": True, "version": "2.1.0", "logged_in": True, "subscription": "pro"}
    assert "someone@example.com" not in str(s)
    assert {"code": "ja", "name": "日文", "status": "supported", "reading_rtl": True} in s["languages"]["sources"]
