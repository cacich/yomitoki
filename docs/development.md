# 開發環境

## 需求

- Windows 10 / 11
- Python 3.11：manga-image-translator 目前只支援 3.10–3.11。可以用 [uv](https://github.com/astral-sh/uv) 安裝，`uv python install 3.11`
- NVIDIA 顯卡（選用）：建議 4 GB VRAM 以上；沒有顯卡會自動改用 CPU，每頁慢上好幾倍
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)：安裝後在終端機執行 `claude` 登入一次
- Visual Studio 2022 的「使用 C++ 的桌面開發」：`pydensecrf2` 在 Windows + Python 3.11 沒有預編譯 wheel，需要從原始碼編譯

## 安裝

```powershell
uv venv --python 3.11 .venv
# 1. PyTorch（CUDA 12.6）；沒有 NVIDIA 顯卡時改用 https://download.pytorch.org/whl/cpu
uv pip install --python .venv\Scripts\python.exe torch torchvision --index-url https://download.pytorch.org/whl/cu126
# 2. manga-image-translator 的依賴
$env:PYTHONUTF8 = "1"                        # pydensecrf2 的 setup.py 在中文 Windows 上需要
$env:UV_INSECURE_NO_ZIP_VALIDATION = "1"     # 上游的 rusty-manga-image-translator wheel 內有重複的 RECORD
uv pip install --python .venv\Scripts\python.exe -r requirements\mit.txt
# 3. Yomitoki 本身
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
# 4. manga-image-translator 原始碼（固定在 commit 441d07c）
.venv\Scripts\python scripts\install-engine.py
# 5. 下載模型與字型（約 1.5 GB）
.venv\Scripts\yomitoki setup
```

manga-image-translator 不能直接 `pip install`：上游的 `setup.cfg` 只打包最上層的 `manga_translator`，子套件不會被裝進去。
`install-engine.py` 會下載固定版本的原始碼到 `%LOCALAPPDATA%\Yomitoki\vendor\`，用 `.pth` 檔加進 Python 的搜尋路徑。
它也會刪掉上游附帶、不能再散布的字型檔。

如果公司或學校網路會攔截 HTTPS，uv 會出現 `invalid peer certificate: UnknownIssuer`。這時加上 `--native-tls`，或設定 `UV_NATIVE_TLS=1`，改用 Windows 的憑證庫。Yomitoki 下載模型時會自動透過 `truststore` 使用 Windows 憑證庫。

## 檔案放在哪裡

| 內容 | 位置 | 可用環境變數覆蓋 |
| --- | --- | --- |
| 作品資料（截圖、OCR、譯文、詞彙表） | `文件\Yomitoki\series\` | `YOMITOKI_HOME` |
| 自訂素材 | `文件\Yomitoki\custom-assets\` | `YOMITOKI_HOME` |
| 模型 | `%LOCALAPPDATA%\Yomitoki\models\` | `YOMITOKI_MODELS` |
| manga-image-translator 原始碼 | `%LOCALAPPDATA%\Yomitoki\vendor\` | `YOMITOKI_APP_HOME` |
| 嵌字字型 | `%LOCALAPPDATA%\Yomitoki\fonts\` | `YOMITOKI_APP_HOME` |
| 單張翻譯的工作檔 | `%LOCALAPPDATA%\Yomitoki\work\` | `YOMITOKI_APP_HOME` |

## 常用指令

```powershell
# 單張截圖
yomitoki translate tests\fixtures\ja-page-01.png -o out.png

# 整話
yomitoki series new "作品名"
#   把截圖存成 文件\Yomitoki\series\作品名\ep001\001.png、002.png…
yomitoki episode run "作品名" 1        # OCR → 翻譯 → 嵌字
yomitoki glossary list "作品名" --pending
yomitoki glossary confirm "作品名" タヌ吉 狸吉
yomitoki episode translate "作品名" 1 --force
yomitoki episode render "作品名" 1     # 只重做嵌字，沿用 OCR 與擦字結果

# 本機伺服器（API ＋ 介面）
yomitoki serve
#   介面：http://127.0.0.1:8765（需要先建置 ui，見下方）
#   會改變資料的請求都要帶 X-Yomitoki-Client 標頭（防止其他網站跨站呼叫）
curl.exe -X POST --data-binary "@tests\fixtures\ja-page-01.png" -H "Content-Type: image/png" -H "X-Yomitoki-Client: curl" http://127.0.0.1:8765/translate -o out.png
```

## 介面（ui/）

Vite + React + TypeScript。手繪輪廓用 rough.js，英文字體用 @fontsource 打包在本機；中文介面字型（jf open 粉圓）由後端第一次啟動時下載，網址是 `/fonts/jf-openhuninn.ttf`。

```powershell
cd ui
npm install
npm run build        # 輸出到 ui/dist，yomitoki serve 會直接提供
npm run dev          # 開發模式：http://127.0.0.1:5173，/api 轉給 yomitoki serve
npm test             # 語系檔檢查（兩種語言的 key 一致、程式用到的 key 都存在）
```

介面文字都放在 `ui/src/i18n/zh-TW.json` 與 `en.json`，新增文字時兩個檔案都要加。

## 安裝檔與啟動器（installer/、app/launcher/）

見 [installer/README.md](../installer/README.md)。開發時可以直接從 repo 執行啟動器，用現有的開發環境當執行環境，略過精靈的下載步驟：

```powershell
$env:YOMITOKI_RUNTIME_PYTHON = "$PWD\.venv\Scripts\python.exe"
.venv\Scripts\python -m app.launcher      # 需要先在開發環境裝 pywebview 與 pystray
```

## 瀏覽器插件（extension/）

Chrome Manifest V3，原生 JavaScript，不需要建置。安裝與使用方式見 [extension/README.md](../extension/README.md)。

```powershell
python scripts\sync-shared.py   # 把 tokens.css 與插件圖示複製進 extension/
node --test extension\lib.test.mjs  # 純函式的單元測試
```

整話也可以在 Claude Code 裡翻：先執行 `yomitoki episode ocr`，再輸入 `/translate-episode 作品名 1`。

## 效能參考

以 GTX 1650（4 GB VRAM）處理 1200 × 1700 的測試頁：

| 步驟 | 時間 |
| --- | --- |
| 偵測與 OCR | 約 5 秒 |
| 擦字與嵌字 | 約 2 秒 |
| 只改譯文後重新嵌字（沿用擦字快取） | 約 0.3 秒 |
| Claude Code 翻譯（7 個對話框） | 約 12 秒 |

顯示卡記憶體：模型常駐約 1.1 GB，翻譯時峰值約 2.7 GB。每件工作結束後會釋放 PyTorch 的快取。

擦字尺寸依顯示卡記憶體自動決定：4 GB 以下用 1024，8 GB 以下用 1536，更大的用 2048（`app/engine.py` 的 `auto_inpainting_size`）。
4 GB 的卡用 1536 時峰值會到 4.3 GB，超過實體容量；如果這張卡同時負責桌面顯示，整台電腦都會變卡。

## 測試

```powershell
.venv\Scripts\python -m pytest                     # 單元測試，不需要顯卡與 Claude Code
.venv\Scripts\python -m pytest -m gpu              # 實際跑偵測、OCR、擦字、嵌字
.venv\Scripts\python -m pytest -m "gpu and claude" # 再加上實際呼叫 claude -p（消耗訂閱額度）
```

測試圖 `tests/fixtures/ja-page-01.png` 由 `scripts/make-test-page.py` 產生，內容是原創插畫與台詞。**不要把任何真實漫畫的截圖放進 repo。**

## 授權注意

manga-image-translator 的 repo 裡附了 `msyh.ttc`、`msgothic.ttc`、`Arial-Unicode-Regular.ttf` 等字型，這些不能再散布。
Yomitoki 不使用它們：嵌字時把 renderer 的備援字型換成 OFL 授權的 Noto CJK（見 `app/engine.py`）。
