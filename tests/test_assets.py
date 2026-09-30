import json
import os
import time
from pathlib import Path

import pytest

from app import paths
from app.assets import AssetRegistry, UnknownAssetError, UnsupportedFormatError, image_size, sniff_format

def make_png(path: Path, w: int, h: int) -> Path:
    from PIL import Image

    Image.new("RGBA", (w, h), (217, 139, 106, 255)).save(path)
    return path


@pytest.fixture
def reg(tmp_path):
    return AssetRegistry(custom_dir=tmp_path / "custom-assets")


def test_manifest_defaults_all_exist():
    reg = AssetRegistry()
    manifest = json.loads((paths.BUILTIN_ASSETS_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert set(reg.specs) == set(manifest["assets"])
    for asset_id in reg.specs:
        p = reg.default_path(asset_id)
        assert p.is_file(), f"{asset_id} 的預設檔 {p} 不存在"
        assert sniff_format(p) == p.suffix.lstrip(".")


def test_plan_asset_ids_present():
    expected = {
        "app-icon", "extension-icon", "mascot-welcome", "mascot-guide", "mascot-loading",
        "mascot-error", "empty-shelf", "empty-series", "paper-texture", "readme-hero",
    }
    assert expected <= set(AssetRegistry().specs)


def test_resolve_falls_back_to_default(reg):
    assert reg.resolve("mascot-welcome") == reg.default_path("mascot-welcome")
    assert reg.inspect("mascot-welcome").source == "default"


def test_custom_file_overrides_default(reg):
    reg.custom_dir.mkdir(parents=True)
    custom = make_png(reg.custom_dir / "mascot-welcome.png", 1600, 1600)
    assert reg.resolve("mascot-welcome") == custom
    info = reg.inspect("mascot-welcome")
    assert info.source == "custom"
    assert info.pixel_size == (1600, 1600)
    assert info.warnings == []


def test_newest_custom_format_wins(reg):
    reg.custom_dir.mkdir(parents=True)
    old = make_png(reg.custom_dir / "mascot-guide.png", 400, 400)
    new = reg.custom_dir / "mascot-guide.svg"
    new.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>', encoding="utf-8")
    past = time.time() - 60
    os.utime(old, (past, past))
    assert reg.resolve("mascot-guide") == new


def test_replace_and_restore(reg, tmp_path):
    src = make_png(tmp_path / "gpt-tanuki.png", 800, 800)
    target = reg.replace("mascot-error", src)
    assert target == reg.custom_dir / "mascot-error.png"
    assert reg.resolve("mascot-error") == target

    # 換成另一種格式時，舊的自訂檔要移除，避免同時存在兩份
    svg = tmp_path / "error.svg"
    svg.write_text('<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    reg.replace("mascot-error", svg)
    assert not target.exists()

    reg.restore_default("mascot-error")
    assert reg.resolve("mascot-error") == reg.default_path("mascot-error")


def test_replace_rejects_bad_files(reg, tmp_path):
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"\xff\xd8\xff")
    with pytest.raises(UnsupportedFormatError):
        reg.replace("mascot-error", jpg)
    fake = tmp_path / "fake.png"
    fake.write_text("not a png")
    with pytest.raises(UnsupportedFormatError):
        reg.replace("mascot-error", fake)


def test_inspect_warns_on_low_resolution_and_ratio(reg):
    reg.custom_dir.mkdir(parents=True)
    make_png(reg.custom_dir / "empty-shelf.png", 600, 600)
    warnings = reg.inspect("empty-shelf").warnings
    assert any("解析度" in w for w in warnings)
    assert any("比例" in w for w in warnings)


def test_unknown_asset(reg):
    with pytest.raises(UnknownAssetError):
        reg.resolve("does-not-exist")


def test_image_size_webp(tmp_path):
    from PIL import Image

    p = tmp_path / "x.webp"
    Image.new("RGBA", (321, 123), (0, 0, 0, 0)).save(p, format="WEBP", lossless=True)
    assert image_size(p) == (321, 123)
    assert sniff_format(p) == "webp"


def test_data_home_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YOMITOKI_HOME", str(tmp_path))
    assert paths.custom_assets_dir() == tmp_path / "custom-assets"
