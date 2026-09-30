# Third-party notices

Licenses were checked against each project's repository on 2026-09-30.
Re-check them before bundling a new version.

| Component | Used for | License | Bundled |
| --- | --- | --- | --- |
| [manga-image-translator](https://github.com/zyddnys/manga-image-translator) @ `441d07c` | Text detection, inpainting, typesetting | GPL-3.0 | Downloaded at setup (not in this repo) |
| [manga-ocr](https://github.com/kha-white/manga-ocr) | Japanese OCR | Apache-2.0 | Installed as a dependency |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | OCR for other languages | Apache-2.0 | Planned (v0.2) |
| [OpenCC](https://github.com/BYVoid/OpenCC) | Taiwan Traditional Chinese normalization (`s2twp`) | Apache-2.0 | Installed as a dependency |
| [FastAPI](https://github.com/fastapi/fastapi) | Local backend | MIT | Installed as a dependency |
| [truststore](https://github.com/sethmlarson/truststore) | Uses the Windows certificate store for downloads | MIT | Installed as a dependency |
| [pydensecrf2](https://pypi.org/project/pydensecrf2/) 1.1 | Mask refinement, required by manga-image-translator. A prebuilt Windows wheel is in `installer/wheels/` (PyPI only ships source) | MIT | Bundled wheel |
| [pywebview](https://github.com/r0x0r/pywebview) 6.2.1 | Desktop window and first-run wizard | BSD-3-Clause | Downloaded at install |
| [pythonnet](https://github.com/pythonnet/pythonnet) 3.2.0 / [clr-loader](https://github.com/pythonnet/clr-loader) | Used by pywebview on Windows | MIT | Downloaded at install |
| [bottle](https://github.com/bottlepy/bottle), [proxy-tools](https://pypi.org/project/proxy-tools/) | Used by pywebview | MIT | Downloaded at install |
| [pystray](https://github.com/moses-palmer/pystray) 0.19.5 | System tray icon | LGPL-3.0 | Downloaded at install |
| [uv](https://github.com/astral-sh/uv) 0.12.21 | Python environment manager; `uv.exe` is bundled in the installer | MIT OR Apache-2.0 | Bundled |
| [CPython](https://www.python.org/) 3.11.16 | Runtime, downloaded by uv from [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | PSF-2.0 | Downloaded at install |
| [PyTorch](https://pytorch.org/) 2.14.0 | Inference (CUDA 12.6 or CPU build) | BSD-3-Clause | Downloaded at install |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Builds the installer (not redistributed; its translation file `installer/ChineseTraditional.isl` is) | Inno Setup License | Build tool |
| [rough.js](https://github.com/rough-stuff/rough) | Hand-drawn UI outlines | MIT | Planned (M3) |
| [Pillow](https://github.com/python-pillow/Pillow) | Icon build script | MIT-CMU (HPND) | Dev only |
| [resvg-py](https://github.com/baseplate-admin/resvg-py) | SVG rasterization in the icon build script | MIT | Dev only |

## Fonts

| Font | Used for | License |
| --- | --- | --- |
| [jf open 粉圓 (open huninn)](https://github.com/justfont/open-huninn-font) | Chinese UI text | SIL OFL 1.1. Its Hanzi are derived from Kosugi Maru (Apache-2.0). "open huninn" and "huninn" are Reserved Font Names. |
| [Noto Sans CJK / Noto Sans TC, JP, KR](https://github.com/notofonts/noto-cjk) | Text typeset into translated pages | SIL OFL 1.1 |
| [Fraunces](https://github.com/google/fonts/tree/main/ofl/fraunces) | English display headings | SIL OFL 1.1 |
| [Nunito](https://github.com/google/fonts/tree/main/ofl/nunito) | English body text | SIL OFL 1.1 |
| [Caveat](https://github.com/google/fonts/tree/main/ofl/caveat) | Handwritten English notes | SIL OFL 1.1 |

Typesetting fonts (Noto Sans TC / JP / KR, subset OTF from tag `Sans2.004`) are downloaded to `%LOCALAPPDATA%\Yomitoki\fonts\` on first use, together with their OFL license file.

manga-image-translator's repository also contains `msyh.ttc`, `msgothic.ttc` and `Arial-Unicode-Regular.ttf`. These are not redistributable. Yomitoki deletes them after download and never uses them.

All of the above are compatible with distributing Yomitoki under GPL-3.0.
