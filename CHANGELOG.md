# Changelog

All notable changes to Yomitoki are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-30

First release. Windows only, Japanese → Traditional Chinese (Taiwan), page-by-page manga.

### Added

- **Translation core**: text detection, OCR (manga-ocr), inpainting (LaMa) and typesetting, built on a pinned [manga-image-translator](https://github.com/zyddnys/manga-image-translator).
  - Vertical Chinese typesetting with CJK line-breaking rules (no closing punctuation at the start of a column).
  - Only the recognized text is sent for translation; screenshots never leave the computer.
- **Translation through your own Claude Code** (`claude -p`, no API key, tools disabled, structured JSON output). OpenCC `s2twp` normalization that never changes confirmed glossary terms.
- **Per-series memory**: glossary with pending / confirmed terms, tone and honorific rules, plot summary. New proper nouns are proposed as pending until you confirm them.
- **App UI** (hand-drawn editorial style, day and night mode, zh-TW / English): shelf, series page with drag-and-drop screenshots and one-click episode translation, reader (hold Space to peek at the original, right-to-left page turns), glossary and rules editor, settings with GPU / Claude Code status and replaceable artwork.
- **Chrome extension**: press `Alt+Shift+Y` to capture the visible tab and see the translation in the side panel, or save pages into an episode to translate later. Minimal permissions (`activeTab`, `sidePanel`, `storage`, local server only).
- **Installer** (`Yomitoki-Setup-0.1.0.exe`, ~15 MB, no admin rights) with a first-run wizard that checks the computer, downloads the components and models, connects Claude Code, walks through the extension, creates the first series and translates a sample page.
- Command line (`yomitoki translate / series / episode / glossary / serve`) and a local API bound to `127.0.0.1`, protected against DNS rebinding and cross-site requests.
- `/translate-episode` command for translating a whole episode inside Claude Code.

### Performance

- On a GTX 1650 (4 GB, shared with the desktop): about 5 s OCR, 2 s inpainting and typesetting, 0.3 s to re-typeset after editing a translation. Claude Code translation time comes on top.
- Inpainting size is chosen from the available VRAM, and the GPU cache is released after every job so the desktop stays responsive.

### Known limitations

- Windows 10 / 11 (64-bit) only. Tested on one machine with an NVIDIA GTX 1650; CPU mode works but is several times slower.
- Japanese → Traditional Chinese only. Vertical-scroll (webtoon) mode and Korean are planned for 0.2; more languages for 0.3.
- The extension is not on the Chrome Web Store; it is loaded as an unpacked extension.
- Some error messages from the engine are shown in Chinese even when the UI is in English.
- Pages that were added by mistake have to be deleted from the series folder by hand.

[0.1.0]: https://github.com/cacich/yomitoki/releases/tag/v0.1.0
