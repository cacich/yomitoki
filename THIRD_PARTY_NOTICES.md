# Third-party notices

Licenses were checked against each project's repository on 2026-09-30.
Re-check them before bundling a new version.

| Component | Used for | License | Bundled |
| --- | --- | --- | --- |
| [manga-image-translator](https://github.com/zyddnys/manga-image-translator) | Text detection, inpainting, typesetting | GPL-3.0 | Planned (M2) |
| [manga-ocr](https://github.com/kha-white/manga-ocr) | Japanese OCR | Apache-2.0 | Planned (M2) |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | OCR for other languages | Apache-2.0 | Planned (v0.2) |
| [OpenCC](https://github.com/BYVoid/OpenCC) | Taiwan Traditional Chinese normalization (`s2twp`) | Apache-2.0 | Planned (M2) |
| [FastAPI](https://github.com/fastapi/fastapi) | Local backend | MIT | Planned (M2) |
| [pywebview](https://github.com/r0x0r/pywebview) | Desktop window | BSD-3-Clause | Planned (M5) |
| [uv](https://github.com/astral-sh/uv) | Python environment manager used by the installer | Apache-2.0 | Planned (M5) |
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

When a font is bundled, its `OFL.txt` goes next to the font files under `assets/fonts/<font>/`.

All of the above are compatible with distributing Yomitoki under GPL-3.0.
