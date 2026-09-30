import re
from pathlib import Path

from app.assets import AssetRegistry

ROOT = Path(__file__).resolve().parent.parent


def test_brand_page_lists_every_asset():
    html = (ROOT / "docs" / "brand.html").read_text(encoding="utf-8")
    listed = set(re.findall(r'\["([a-z-]+)", "', html.split("const ASSETS", 1)[1].split("];", 1)[0]))
    assert listed == set(AssetRegistry().specs)
