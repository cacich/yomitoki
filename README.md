<p align="center">
  <img src="assets/icons/social-preview.png" alt="Yomitoki: a cozy, local-first reader that translates the manga screenshots you take yourself" width="720">
</p>

<p align="center">
  <img src="assets/icons/app-icon-128.png" alt="Yomitoki icon" width="64"><br>
  <b>Yomitoki（よみとき・讀解）</b><br>
  English · <a href="README.zh-TW.md">繁體中文</a>
</p>

Yomitoki is a personal, multilingual manga reading tool. It runs OCR, translation and typesetting on screenshots **you take yourself**, then lets you read the result in a local, hand-drawn-style reader.

> **Status: pre-alpha.** M1 (skeleton and brand), M2 (translation core), M3 (UI), M4 (Chrome extension, see [extension/README.md](extension/README.md)) and M5 (installer and first-run wizard) are done. Next is the M6 v0.1 release.

<p align="center">
  <img src="docs/screenshots/before-after.png" alt="Left: an original Japanese sample page. Right: Yomitoki's output with the Japanese removed and Traditional Chinese typeset vertically" width="760">
</p>

## Screenshots

All screenshots use original sample pages and artwork.

| Shelf | Series page |
| --- | --- |
| <img src="docs/screenshots/shelf.png" alt="Shelf: magazine-cover heading and series cards" width="400"> | <img src="docs/screenshots/series.png" alt="Series page: series info on the left, episodes with hand-drawn progress bars on the right" width="400"> |
| **Reader** | **Glossary & rules** |
| <img src="docs/screenshots/reader.png" alt="Reader: the page centered, toolbar in the top-right corner" width="400"> | <img src="docs/screenshots/glossary.png" alt="Glossary: notebook-style term list and tone rules" width="400"> |

## Usage notice

Yomitoki is for **personal reading and comprehension only**.

- You are responsible for following the terms of service of any site you read on, and the copyright law where you live.
- **Do not distribute translated output.** Keep it on your own computer.
- Yomitoki only processes screenshots you capture yourself. It does not download, intercept or reconstruct images from websites. It contains no code that targets any particular site.

## How it works

1. Press a hotkey in the browser extension to capture what is on screen.
2. The local backend (bound to `127.0.0.1` only) detects speech bubbles and runs OCR.
3. Only the recognized text is sent for translation, through **your own logged-in Claude Code** (no API key needed). Screenshots never leave your computer.
4. The original text is removed, the translation is typeset back into the page, and the result opens in the reader.

Each series keeps its own memory: a glossary, style rules and a plot summary. Character names therefore stay consistent. New terms are held as "pending" until you confirm them.

## Roadmap

| Version | Features |
| --- | --- |
| v0.1 | Page manga translation (single page or whole episode), language plug-in architecture, Japanese → Traditional Chinese, per-series memory, Claude Code translation, local reader |
| v0.2 | Vertical-scroll (webtoon) mode, Korean → Traditional Chinese, re-apply glossary without re-running OCR |
| v0.3 | English and Chinese sources; English, Japanese and Korean targets; English UI |

Development milestones: M1 skeleton and brand ✅ · M2 translation core ✅ · M3 UI ✅ · M4 browser extension ✅ · M5 installer ✅ · M6 v0.1 release.

## Customizing the look

The illustrations, mascot and icons are all **replaceable assets**. The UI loads images by asset ID, never by hard-coded file name.

1. Find the asset ID and recommended size in [`assets/manifest.json`](assets/manifest.json), for example `mascot-welcome` (800 × 800, transparent).
2. Save your image as `Documents\Yomitoki\custom-assets\mascot-welcome.png`. SVG, PNG and WebP all work. For raster images, use twice the recommended size.
3. Your image replaces the default. If the size or ratio differs, it is scaled to fit and centered, never cropped or stretched. To go back, delete the file.

To rebuild every icon size from a new source image:

```bash
python scripts/build-icons.py --source path/to/my-icon.png
```

## Installing

You need Windows 10 / 11 (64-bit) and [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). An NVIDIA graphics card is recommended; without one Yomitoki still works, just more slowly.

1. Download `Yomitoki-Setup-<version>.exe` from the [Releases page](https://github.com/cacich/yomitoki/releases) and run it. No administrator rights are needed; it installs to `%LOCALAPPDATA%\Yomitoki` by default.
2. Open Yomitoki. The first-run wizard checks your computer, downloads the components and models (about 3–5 GB), connects Claude Code, walks you through the browser extension, creates your first series and translates a sample page.
3. Afterwards, open it from the Start menu or the desktop shortcut. Closing the window only minimizes it to the tray; choose "Quit Yomitoki" in the tray to stop it.

How the installer works and how to build it: [installer/README.md](installer/README.md).

## Command line

In a development environment ([docs/development.md](docs/development.md)) you can also use the command line:

```bash
yomitoki translate page.png -o translated.png
yomitoki series new "My Series"
yomitoki episode run "My Series" 1
```

## Development

Requirements: Python 3.11 (manga-image-translator does not support 3.12 yet), and Node.js 20+ from M3 on. See [docs/development.md](docs/development.md) for the full setup.

```bash
.venv\Scripts\python -m pytest            # unit tests, no GPU or Claude Code needed
.venv\Scripts\python -m pytest -m gpu     # runs the real detection / OCR / inpainting models
```

Useful scripts:

| Script | What it does |
| --- | --- |
| `scripts/check-contrast.py` | Checks that every text and background pair in `ui/src/styles/tokens.css` passes WCAG AA, in both light and night mode |
| `scripts/build-icons.py` | Builds `.ico` and `.png` icons for Windows, the tray, the extension, favicons and the social preview |
| `scripts/make-default-art.py` | Regenerates the default hand-drawn SVG artwork |

Open [`docs/brand.html`](docs/brand.html) in a browser to see the palette, typography and every default asset on one page.

## License

- Code: [GPL-3.0](LICENSE). Yomitoki builds on manga-image-translator, which is GPL-3.0.
- Default artwork in `assets/`: [CC BY 4.0](assets/LICENSE.md).
- Third-party components and fonts: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
