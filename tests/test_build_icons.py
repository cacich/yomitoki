import importlib.util
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def load_builder():
    spec = importlib.util.spec_from_file_location("build_icons", ROOT / "scripts" / "build-icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_from_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("YOMITOKI_HOME", str(tmp_path / "home"))  # 不讀到真正的自訂素材
    assert load_builder().main(["--out", str(tmp_path / "icons")]) == 0
    out = tmp_path / "icons"
    assert sorted(Image.open(out / "app.ico").info["sizes"]) == [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    assert sorted(Image.open(out / "tray.ico").info["sizes"]) == [(16, 16), (32, 32)]
    for s in (16, 32, 48, 128):
        assert Image.open(out / "extension" / f"icon-{s}.png").size == (s, s)
    assert Image.open(out / "social-preview.png").size == (1280, 640)
    assert Image.open(out / "apple-touch-icon-180.png").size == (180, 180)
    assert (out / "favicon.svg").is_file()


def test_png_source_is_letterboxed_not_distorted(tmp_path, monkeypatch):
    monkeypatch.setenv("YOMITOKI_HOME", str(tmp_path / "home"))
    src = tmp_path / "wide.png"
    Image.new("RGBA", (1024, 512), (217, 139, 106, 255)).save(src)
    img = load_builder().render(src, 256)
    assert img.size == (256, 256)
    # 上下留透明邊、中間是圖：沒有被拉伸
    assert img.getpixel((128, 10))[3] == 0
    assert img.getpixel((128, 128))[3] == 255


def test_custom_asset_is_used(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "custom-assets").mkdir(parents=True)
    Image.new("RGBA", (1024, 1024), (0, 128, 0, 255)).save(home / "custom-assets" / "app-icon.png")
    monkeypatch.setenv("YOMITOKI_HOME", str(home))
    assert load_builder().main(["--out", str(tmp_path / "icons")]) == 0
    png = Image.open(tmp_path / "icons" / "app-icon-256.png").convert("RGBA")
    assert png.getpixel((128, 128)) == (0, 128, 0, 255)
