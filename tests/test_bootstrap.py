"""首次啟動精靈的「下載元件」：用假的指令執行器測步驟、參數與進度，不真的下載。"""

import json
from pathlib import Path

import pytest

from app import bootstrap as bs
from app import engine_install


@pytest.fixture
def layout(tmp_path):
    root = tmp_path / "Yomitoki"
    program = root / "program"
    (program / "requirements").mkdir(parents=True)
    (program / "requirements" / "runtime.lock.txt").write_text("numpy==1.26.4\n", encoding="utf-8")
    (program / "installer" / "wheels").mkdir(parents=True)
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "uv.exe").write_bytes(b"")
    return bs.Layout(root, program)


class FakeRunner:
    """記錄每個指令，並模擬 uv 的副作用（建立 Python 與環境）。"""

    def __init__(self, layout, fail_on=None):
        self.layout = layout
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, cmd, env, on_line, cwd=None):
        self.calls.append({"cmd": cmd, "env": env, "cwd": cwd})
        on_line("working…")
        if self.fail_on and self.fail_on in cmd:
            raise RuntimeError(f"{self.fail_on} failed")
        if cmd[1:3] == ["python", "install"]:
            py = self.layout.python_dir / f"cpython-{bs.PYTHON_VERSION}-windows-x86_64-none"
            py.mkdir(parents=True)
            (py / "python.exe").write_bytes(b"")
        if cmd[1] == "venv":
            env_dir = Path(cmd[-1])
            (env_dir / "Scripts").mkdir(parents=True)
            (env_dir / "Scripts" / "python.exe").write_bytes(b"")
            (env_dir / "Lib" / "site-packages").mkdir(parents=True)
            # uv 預設指向次版本 junction
            (env_dir / "pyvenv.cfg").write_text("home = C:\\x\\cpython-3.11-windows-x86_64-none\nversion_info = 3.11\n",
                                                encoding="utf-8")


def test_full_install_sequence_cuda(layout, monkeypatch):
    monkeypatch.setattr(engine_install, "download_source", lambda root, progress=None: root / "vendor" / "mit")
    runner = FakeRunner(layout)
    inst = bs.RuntimeInstaller(layout, "cuda", runner=runner)
    inst.run()
    assert inst.progress.status == "done", inst.progress.error
    assert inst.progress.fraction == pytest.approx(1.0)

    cmds = [c["cmd"] for c in runner.calls]
    assert cmds[0][1:3] == ["python", "install"] and "--no-registry" in cmds[0]
    assert cmds[1][1] == "venv"
    pkgs = cmds[2]
    assert "--no-deps" in pkgs and str(layout.runtime_lock) in pkgs and str(layout.wheels) in pkgs
    torch = cmds[3]
    assert "torch==2.14.0+cu126" in torch and torch[torch.index("--index-url") + 1].endswith("/cu126")
    setup = runner.calls[4]
    assert setup["cmd"][1:4] == ["-m", "app", "setup"] and setup["cwd"] == layout.program

    env = runner.calls[2]["env"]
    assert env["UV_SYSTEM_CERTS"] == "1" and env["UV_PYTHON_INSTALL_DIR"] == str(layout.python_dir)
    assert env["UV_INSECURE_NO_ZIP_VALIDATION"] == "1" and env["PYTHONUTF8"] == "1"
    assert env["YOMITOKI_APP_HOME"] == str(layout.root)

    # 環境指向實際的 Python 資料夾，不經過 junction
    cfg = (layout.runtime_env / "pyvenv.cfg").read_text(encoding="utf-8")
    assert cfg.splitlines()[0] == f"home = {layout.python_dir / f'cpython-{bs.PYTHON_VERSION}-windows-x86_64-none'}"
    assert "version_info = 3.11" in cfg

    info = json.loads(layout.marker.read_text(encoding="utf-8"))
    assert info["device"] == "cuda" and bs.is_ready(layout)


def test_cpu_uses_cpu_wheels(layout, monkeypatch):
    monkeypatch.setattr(engine_install, "download_source", lambda root, progress=None: root / "vendor" / "mit")
    runner = FakeRunner(layout)
    bs.RuntimeInstaller(layout, "cpu", runner=runner).run()
    torch = next(c["cmd"] for c in runner.calls if any("torch==" in a for a in c["cmd"]))
    assert "torch==2.14.0+cpu" in torch and torch[torch.index("--index-url") + 1].endswith("/cpu")


def test_failure_is_reported_not_raised(layout):
    runner = FakeRunner(layout, fail_on="venv")
    inst = bs.RuntimeInstaller(layout, "cuda", runner=runner)
    inst.run()
    assert inst.progress.status == "error"
    assert "venv failed" in inst.progress.error
    assert not bs.is_ready(layout)
    assert "錯誤" in (layout.logs / "setup.log").read_text(encoding="utf-8")


def test_ready_marker_invalidated_when_lock_changes(layout, monkeypatch):
    monkeypatch.setattr(engine_install, "download_source", lambda root, progress=None: root / "vendor" / "mit")
    bs.RuntimeInstaller(layout, "cuda", runner=FakeRunner(layout)).run()
    assert bs.is_ready(layout)
    # 更新程式後鎖定檔變了：要重新安裝執行環境
    layout.runtime_lock.write_text("numpy==2.0.0\n", encoding="utf-8")
    assert not bs.is_ready(layout)


def test_model_download_retries_after_dropped_connection(layout, monkeypatch):
    """模型下載偶爾會在中途斷線；上游會從 .part 續傳，所以自動重試就好。"""
    monkeypatch.setattr(engine_install, "download_source", lambda root, progress=None: root / "vendor" / "mit")
    monkeypatch.setattr(bs.time, "sleep", lambda s: None)
    base = FakeRunner(layout)
    failures = {"left": 2}

    def flaky(cmd, env, on_line, cwd=None):
        if cmd[1:4] == ["-m", "app", "setup"] and failures["left"]:
            failures["left"] -= 1
            raise RuntimeError("ChunkedEncodingError: Connection broken")
        return base(cmd, env, on_line, cwd)

    inst = bs.RuntimeInstaller(layout, "cuda", runner=flaky)
    inst.run()
    assert inst.progress.status == "done", inst.progress.error
    assert "重試" in (layout.logs / "setup.log").read_text(encoding="utf-8")


def test_model_download_gives_up_after_max_attempts(layout, monkeypatch):
    monkeypatch.setattr(engine_install, "download_source", lambda root, progress=None: root / "vendor" / "mit")
    monkeypatch.setattr(bs.time, "sleep", lambda s: None)
    inst = bs.RuntimeInstaller(layout, "cuda", runner=FakeRunner(layout, fail_on="setup"))
    inst.run()
    assert inst.progress.status == "error"


def test_unknown_device_rejected(layout):
    with pytest.raises(ValueError):
        bs.RuntimeInstaller(layout, "tpu")


def test_environment_check(layout, monkeypatch):
    monkeypatch.setattr(bs, "detect_gpu", lambda: {"nvidia": False, "name": None, "vram_gb": None})
    env = bs.environment_check(layout)
    assert env["device"] == "cpu" and env["required_gb"] == bs.REQUIRED_GB["cpu"]
    assert isinstance(env["disk_ok"], bool)


def test_write_pth_uses_locale_encoding(tmp_path):
    """Python 3.11 以系統地區編碼讀 .pth：路徑有中文時要用同一種編碼寫。"""
    import locale

    target = tmp_path / "使用者" / "vendor"
    pth = tmp_path / "x.pth"
    engine_install.write_pth(pth, target)
    enc = locale.getencoding()
    try:
        expected = (str(target) + "\n").encode(enc)
    except UnicodeEncodeError:
        pytest.skip(f"系統編碼 {enc} 表示不了中文，會改用短路徑")
    assert pth.read_bytes() == expected
