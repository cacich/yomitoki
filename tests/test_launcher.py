"""啟動器與首次啟動精靈的 Python 端（不開視窗）。"""

import base64
import re
from pathlib import Path

import pytest

from app.bootstrap import Layout
from app.launcher import runtime
from app.launcher.setup_api import SetupApi

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "launcher" / "web"


@pytest.fixture
def layout(tmp_path):
    return Layout(tmp_path / "Yomitoki", ROOT)


def test_state_and_pid_files(layout):
    assert runtime.load_state(layout) == {}
    runtime.save_state(layout, setup_done=True)
    assert runtime.load_state(layout)["setup_done"] is True
    runtime.write_pid(layout, "server", 1234)
    assert (layout.root / "run" / "server.pid").read_text() == "1234"
    runtime.clear_pid(layout, "server")
    assert not (layout.root / "run" / "server.pid").exists()


def test_detect_layout_dev_and_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("YOMITOKI_APP_HOME", str(tmp_path / "home"))
    # 開發版：直接從 repo 執行
    lay = runtime.detect_layout()
    assert lay.program == ROOT and lay.root == tmp_path / "home"
    # 安裝版：<安裝位置>\program，旁邊有 bin\
    installed = tmp_path / "Yomitoki"
    (installed / "bin").mkdir(parents=True)
    monkeypatch.setattr(runtime.paths, "REPO_ROOT", installed / "program")
    lay = runtime.detect_layout()
    assert lay.root == installed and lay.program == installed / "program"
    import os

    assert os.environ["YOMITOKI_APP_HOME"] == str(installed)


def test_server_start_reports_missing_runtime(layout, monkeypatch):
    monkeypatch.setattr(runtime, "health", lambda timeout=1.5: None)
    monkeypatch.delenv("YOMITOKI_RUNTIME_PYTHON", raising=False)
    s = runtime.ServerProcess(layout)
    s.start()
    assert s.error and "找不到執行環境" in s.error and not s.running


def test_server_reuses_running_instance(layout, monkeypatch):
    monkeypatch.setattr(runtime, "health", lambda timeout=1.5: {"status": "ok"})
    s = runtime.ServerProcess(layout)
    s.start()
    assert s.error is None and s.proc is None
    assert s.wait_ready(timeout=1)


def test_setup_api_assets_and_info(layout, tmp_path, monkeypatch):
    monkeypatch.setenv("YOMITOKI_HOME", str(tmp_path / "docs"))
    api = SetupApi(layout, runtime.ServerProcess(layout))
    url = api.asset("mascot-welcome")
    assert url.startswith("data:image/svg+xml;base64,")
    assert b"<svg" in base64.b64decode(url.split(",", 1)[1])
    assert api.asset("no-such-asset") == ""
    info = api.info()
    assert info["extension_dir"].endswith("extension") and info["locale"] in ("zh-TW", "en")
    langs = api.languages()
    assert {"code": "ja", "name": "日文"} in langs["sources"]


def test_setup_api_finish_marks_setup_done(layout):
    called = []
    api = SetupApi(layout, runtime.ServerProcess(layout), on_finish=lambda: called.append(True))
    api.finish()
    assert runtime.load_state(layout)["setup_done"] is True


def test_setup_api_claude_status_hides_email(layout, monkeypatch):
    import subprocess

    import app.launcher.setup_api as sa

    monkeypatch.setattr(sa.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)

    def fake_run(cmd, **kw):
        out = '{"loggedIn": true, "subscriptionType": "pro", "email": "a@b.c"}' if "auth" in cmd else "2.1.0 (Claude Code)"
        return subprocess.CompletedProcess(cmd, 0, out, "")

    monkeypatch.setattr(sa.subprocess, "run", fake_run)
    s = SetupApi(layout, runtime.ServerProcess(layout)).claude_status()
    assert s == {"installed": True, "logged_in": True, "subscription": "pro", "version": "2.1.0"}


def test_trial_sample_exists():
    assert (ROOT / "assets" / "samples" / "ja-page-01.png").is_file()


def test_wizard_tokens_in_sync():
    assert (WEB / "tokens.css").read_bytes() == (ROOT / "ui" / "src" / "styles" / "tokens.css").read_bytes(), \
        "tokens.css 不同步：請執行 python scripts/sync-shared.py"


def test_wizard_messages_complete():
    """精靈頁面用到的每個文字 key，繁中與英文都要有；呼叫的 API 方法都要存在。"""
    html = (WEB / "setup.html").read_text(encoding="utf-8")
    js = (WEB / "setup.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'data-t="([\w.]+)"', html)) | set(re.findall(r'\bt\("([\w.]+)"', js))
    for step in ("python", "venv", "packages", "torch", "engine", "models", "finish"):
        keys.add(f"download.step_{step}")

    # 從 setup.js 取出 MESSAGES，用 node 解析成 JSON 比對（沒有 node 就跳過）
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("需要 node")
    script = js.split("const STEPS")[0] + "\nconsole.log(JSON.stringify(MESSAGES));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    messages = json.loads(out)

    def has(locale, key):
        node_ = messages[locale]
        for part in key.split("."):
            node_ = node_.get(part) if isinstance(node_, dict) else None
        return isinstance(node_, str)

    for locale in ("zh-TW", "en"):
        missing = sorted(k for k in keys if not has(locale, k))
        assert missing == [], (locale, missing)

    public = {m for m in dir(SetupApi) if not m.startswith("_")}
    called = set(re.findall(r"\bapi\.(\w+)\(", js))
    assert called <= public, called - public


def test_installer_script_references_exist():
    iss = (ROOT / "installer" / "yomitoki.iss").read_bytes()
    assert iss.startswith(b"\xef\xbb\xbf"), "yomitoki.iss 要存成 UTF-8 BOM，Inno Setup 才讀得懂中文"
    text = iss.decode("utf-8-sig")
    # Inno Setup 會把行首的 [ 當成區段標題，連 [Code] 裡也一樣
    code = text.split("[Code]", 1)[1]
    assert not re.search(r"^\s+\[", code, re.M)
    assert "PrivilegesRequired=lowest" in text and r"{localappdata}\Yomitoki" in text
    # Inno Setup 6.5 起預設開 RedirectionGuard，子程序繼承後 uv 無法穿過 junction（os error 448）
    assert re.search(r"^RedirectionGuard=no\s*$", text, re.M)
    cmd = (ROOT / "installer" / "bootstrap-launcher.cmd").read_bytes()
    assert cmd.isascii(), "bootstrap-launcher.cmd 只能用 ASCII（cmd.exe 以 OEM 編碼讀批次檔）"
    assert b"\r\n" in cmd and b"\n" not in cmd.replace(b"\r\n", b""), "批次檔要用 CRLF"
    for rel in ("requirements/runtime.lock.txt", "requirements/launcher.lock.txt", "installer/ChineseTraditional.isl"):
        assert (ROOT / rel).is_file(), rel
    wheels = list((ROOT / "installer" / "wheels").glob("pydensecrf2-*-cp311-*win_amd64.whl"))
    assert wheels, "缺少預先編譯的 pydensecrf2 wheel"
