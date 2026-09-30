<p align="center">
  <img src="assets/icons/social-preview.png" alt="Yomitoki：溫暖手繪風的本機漫畫截圖翻譯閱讀工具" width="720">
</p>

<p align="center">
  <img src="assets/icons/app-icon-128.png" alt="Yomitoki 圖示" width="64"><br>
  <b>Yomitoki（よみとき・讀解）</b><br>
  <a href="README.md">English</a> · 繁體中文
</p>

Yomitoki 是個人用的多語言漫畫截圖翻譯閱讀工具：對**你自己截下的畫面**做 OCR、翻譯與嵌字，再用本機的手繪風閱讀器閱讀。

> **目前狀態：pre-alpha。** 已完成 M1（骨架與品牌）、M2（翻譯核心）、M3（介面）、M4（Chrome 插件，見 [extension/README.md](extension/README.md)）與 M5（安裝檔與首次啟動精靈），接下來是 M6 v0.1 發佈。

## 使用聲明

本工具**僅供個人閱讀理解**。

- 使用者須自行遵守各平台的使用條款與所在地的著作權法。
- **翻譯結果不得散布**，請只留在自己的電腦裡。
- Yomitoki 只處理你自己截下的畫面，不下載、不攔截、不還原任何網站上的圖片，也不包含針對特定網站的程式碼。

## 運作方式（規劃中）

1. 在瀏覽器插件按下快捷鍵，擷取目前畫面。
2. 本機後端（只綁 `127.0.0.1`）偵測對話框並做 OCR。
3. 只把辨識出的文字送去翻譯，翻譯透過**你自己登入的 Claude Code** 進行，不需要 API key。截圖本身不會離開你的電腦。
4. 擦除原文、嵌入譯文，在閱讀器裡開啟。

每部作品都有自己的記憶：詞彙表、語氣規則與劇情摘要，讓角色名在每一頁都翻得一樣。新出現的名詞會先標成「待確認」，等你確認後才寫入。

## 版本規劃

| 版本 | 功能 |
| --- | --- |
| v0.1 | 頁漫翻譯（單頁或整話）、語言外掛架構、日文 → 繁中、作品記憶、Claude Code 翻譯、閱讀器 |
| v0.2 | 條漫模式、韓文 → 繁中、修改詞彙表後只重做嵌字 |
| v0.3 | 英文、中文來源；英文、日文、韓文目標；介面英文版 |

開發里程碑：M1 骨架與品牌 ✅ · M2 翻譯核心 ✅ · M3 介面 ✅ · M4 瀏覽器插件 ✅ · M5 安裝 ✅ · M6 v0.1 發佈。

## 自訂外觀

插畫、吉祥物與圖示都是**可替換素材**：介面只透過素材代號讀取圖片，不在程式裡寫死檔名。

1. 在 [`assets/manifest.json`](assets/manifest.json) 找到代號與建議尺寸，例如 `mascot-welcome`（800 × 800，透明背景）。
2. 把圖片存成 `文件\Yomitoki\custom-assets\mascot-welcome.png`。支援 SVG、PNG、WebP；點陣圖請提供建議尺寸的 2 倍解析度。
3. 放好後就會取代預設圖片。尺寸或比例不符時會等比縮放、置中顯示，不裁切也不變形。刪掉檔案即還原預設。

換了主圖示後，重新輸出所有尺寸：

```bash
python scripts/build-icons.py --source path/to/my-icon.png
```

## 安裝

需要 Windows 10 / 11（64 位元）與 [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)。建議有 NVIDIA 顯示卡；沒有也能用，只是比較慢。

1. 執行 `Yomitoki-Setup-<版本>.exe`（不需要系統管理員權限，預設裝到 `%LOCALAPPDATA%\Yomitoki`）。
2. 打開 Yomitoki，首次啟動精靈會帶你：檢查電腦、下載元件與模型（約 3～5 GB）、連接 Claude Code、安裝瀏覽器插件、建立第一部作品、試翻一張。
3. 之後從開始功能表或桌面捷徑打開。關閉視窗只會縮到系統匣；從系統匣選「結束 Yomitoki」才會完全關掉。

安裝檔怎麼運作、怎麼自己建置，見 [installer/README.md](installer/README.md)。

## 命令列

在開發環境裡（見 [docs/development.md](docs/development.md)）也可以直接用命令列：

```bash
yomitoki translate 截圖.png -o 譯圖.png
yomitoki series new "作品名"
yomitoki episode run "作品名" 1
```

## 開發

需要 Python 3.11（manga-image-translator 還不支援 3.12），Node.js 20 以上（M3 起使用）。完整步驟見 [docs/development.md](docs/development.md)。

```bash
.venv\Scripts\python -m pytest            # 單元測試，不需要顯卡與 Claude Code
.venv\Scripts\python -m pytest -m gpu     # 實際跑偵測、OCR、擦字模型
```

| 腳本 | 用途 |
| --- | --- |
| `scripts/check-contrast.py` | 檢查 `ui/src/styles/tokens.css` 所有文字與底色組合，在一般與夜讀模式下都通過 WCAG AA |
| `scripts/build-icons.py` | 輸出 Windows、系統匣、插件、favicon 與社群預覽圖的 ICO / PNG |
| `scripts/make-default-art.py` | 重新產生預設的手繪 SVG 素材 |

用瀏覽器打開 [`docs/brand.html`](docs/brand.html)，可以在同一頁看到色票、字體與所有預設素材。

## 授權

- 程式碼：[GPL-3.0](LICENSE)（直接引用的 manga-image-translator 為 GPL-3.0）
- `assets/` 內的預設圖片：[CC BY 4.0](assets/LICENSE.md)
- 第三方套件與字型：見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
