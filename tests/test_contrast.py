import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_checker():
    spec = importlib.util.spec_from_file_location("check_contrast", ROOT / "scripts" / "check-contrast.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_token_pairs_pass_wcag_aa():
    failed = [r for r in load_checker().check() if not r["ok"]]
    assert not failed, "\n".join(f"{r['theme']} {r['label']}: {r['ratio']:.2f}" for r in failed)


def test_contrast_math():
    cc = load_checker()
    assert round(cc.contrast("#000000", "#ffffff"), 1) == 21.0
    assert round(cc.contrast("#777777", "#ffffff"), 2) == 4.48
