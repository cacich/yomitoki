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
| [pydensecrf2](https://pypi.org/project/pydensecrf2/) | Mask refinement, required by manga-image-translator | MIT | Installed as a dependency |
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

Typesetting fonts (Noto Sans TC / JP / KR, subset OTF from tag `Sans2.004`) are downloaded to `%LOCALAPPDATA%\Yomitoki\fonts\` on first use, together with their OFL license file.

manga-image-translator's repository also contains `msyh.ttc`, `msgothic.ttc` and `Arial-Unicode-Regular.ttf`. These are not redistributable. Yomitoki deletes them after download and never uses them.

All of the above are compatible with distributing Yomitoki under GPL-3.0.
