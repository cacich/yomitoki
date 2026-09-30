"""發佈前的檢查：各處的版本號一致、更新紀錄有這一版。"""

import json
import re
from pathlib import Path

from app import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_versions_match_everywhere():
    pyproject = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    ui = json.loads((ROOT / "ui" / "package.json").read_text(encoding="utf-8"))["version"]
    lock = json.loads((ROOT / "ui" / "package-lock.json").read_text(encoding="utf-8"))
    ext = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))["version"]
    iss = re.search(r'#define AppVersion "([^"]+)"', (ROOT / "installer" / "yomitoki.iss").read_text(encoding="utf-8-sig")).group(1)
    versions = {"app": __version__, "pyproject": pyproject, "ui": ui, "ui-lock": lock["version"],
                "ui-lock-root": lock["packages"][""]["version"], "extension": ext, "installer": iss}
    assert len(set(versions.values())) == 1, versions


def test_changelog_has_current_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[?{re.escape(__version__)}\]?", changelog, re.M), f"CHANGELOG.md 沒有 {__version__}"


def test_readme_screenshots_exist():
    for readme in ("README.md", "README.zh-TW.md"):
        text = (ROOT / readme).read_text(encoding="utf-8")
        for rel in re.findall(r'(?:src="|\]\()(docs/screenshots/[^")]+)', text):
            assert (ROOT / rel).is_file(), f"{readme} 引用的 {rel} 不存在"
