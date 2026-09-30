"""使用者資料位置。

作品資料預設放在「文件\\Yomitoki」，可用環境變數 YOMITOKI_HOME 覆蓋
（之後設定頁也會寫入這個位置）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILTIN_ASSETS_DIR = REPO_ROOT / "assets"


def documents_dir() -> Path:
    """回傳使用者的「文件」資料夾，Windows 上會跟著資料夾重新導向（例如 OneDrive）。"""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            from uuid import UUID

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            u = UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")  # FOLDERID_Documents
            guid = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            out = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32
            if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
                try:
                    return Path(out.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(out)
        except (OSError, AttributeError):
            pass
    return Path.home() / "Documents"


def data_home() -> Path:
    """Yomitoki 的使用者資料根目錄。"""
    override = os.environ.get("YOMITOKI_HOME")
    return Path(override) if override else documents_dir() / "Yomitoki"


def custom_assets_dir() -> Path:
    return data_home() / "custom-assets"
