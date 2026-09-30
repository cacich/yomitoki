# 安裝檔

`Yomitoki-Setup-<版本>.exe` 只有十幾 MB：裡面只有程式本身與 [uv](https://github.com/astral-sh/uv)。
Python、翻譯核心與模型在安裝後才下載，總共約 3～5 GB。

## 安裝流程

1. **安裝檔**（Inno Setup）：預設裝到 `%LOCALAPPDATA%\Yomitoki`，不需要系統管理員權限。
   - 複製程式到 `program\`、uv 到 `bin\`，建立開始功能表與桌面捷徑。
   - 執行 `bootstrap-launcher.cmd`：下載 Python 3.11，建立很小的「啟動器環境」（`env\launcher\`：pywebview、pystray），約 1 分鐘。
2. **首次啟動精靈**（`app/launcher/`，由狸貓帶領，每步一頁）：
   1. 環境檢查：NVIDIA 顯示卡、磁碟空間
   2. 下載元件：建立「執行環境」（`env\runtime\`），安裝 PyTorch（依顯示卡選 CUDA 或 CPU 版）、翻譯核心的套件、manga-image-translator，下載模型
   3. 連接 Claude Code：檢查是否安裝、登入；需要時開終端機讓使用者登入
   4. 安裝瀏覽器插件：打開 `chrome://extensions`，引導載入 `program\extension`
   5. 建立第一部作品
   6. 試翻一張：用內建的原創範例圖跑一次完整流程
3. 之後打開 Yomitoki：啟動器啟動翻譯伺服器、打開視窗；關閉視窗只縮到系統匣，從系統匣選「結束」才會關掉。

為什麼分成兩個環境：翻譯核心有數 GB，而且安裝時會替換 Python 套件；如果跟正在執行的啟動器同一個環境，Windows 會因為檔案被佔用而無法替換。

## 解除安裝

從「設定 → 應用程式」解除安裝。會先結束還在執行的 Yomitoki（依 `run\*.pid`），刪除程式、環境、模型與記錄檔。
`文件\Yomitoki`（截圖、譯圖、詞彙表）預設保留，會先詢問。

## 建置

需要 Node.js（建置介面）與 [Inno Setup 6](https://jrsoftware.org/isinfo.php)。Inno Setup 可以用可攜模式安裝，不需要系統管理員權限：

```powershell
innosetup-6.7.3.exe /PORTABLE=1 /VERYSILENT /CURRENTUSER /DIR=D:\tools\InnoSetup
```

```powershell
python installer\build.py                  # 輸出 installer\build\Output\Yomitoki-Setup-<版本>.exe
python installer\build.py --skip-ui        # 沿用現有的 ui\dist
python installer\build.py --iscc <ISCC.exe 的位置>
```

改過套件版本後，在驗證過的開發環境重新產生鎖定檔：

```powershell
python installer\make-locks.py
```

## 固定的版本與預先編譯的檔案

| 項目 | 版本 | 說明 |
| --- | --- | --- |
| Python | 3.11.16 | manga-image-translator 只支援 3.10–3.11 |
| uv | 0.12.21 | 建置時從 GitHub Release 下載並核對 SHA-256 |
| PyTorch | 2.14.0（cu126 / cpu） | 依顯示卡決定 |
| 其他套件 | `requirements/runtime.lock.txt`、`launcher.lock.txt` | 以 `--no-deps` 安裝，每個人裝到的版本都一樣 |
| `wheels/pydensecrf2-1.1-cp311-cp311-win_amd64.whl` | 1.1 | PyPI 上只有原始碼、需要 C++ 編譯器，所以預先編好。來源：[pydensecrf2](https://pypi.org/project/pydensecrf2/)（MIT） |
| `ChineseTraditional.isl` | Inno Setup 6.7.3 | 非官方的繁體中文安裝介面翻譯，取自 [jrsoftware/issrc](https://github.com/jrsoftware/issrc/tree/is-6_7_3/Files/Languages/Unofficial) |

## 踩過的坑

- **RedirectionGuard**：Inno Setup 6.5 起，Setup 與 Uninstall 預設開啟 Windows 的 RedirectionGuard，而且子程序會繼承。它不讓程序穿過一般使用者建立的 junction，但 uv 管理 Python 需要 junction，結果會出現 os error 448（路徑包含不受信任的掛接點）。
  - 這個防護是為了避免「以系統管理員安裝」時被導向攻擊提權。Yomitoki 只裝在使用者自己的資料夾、不要求系統管理員權限，所以在 `yomitoki.iss` 設 `RedirectionGuard=no`。
  - 保險起見，安裝後也把 `pyvenv.cfg` 改成直接指向實際的 Python 資料夾，不經過 uv 的「次版本」junction（`cpython-3.11-…`）。
- **`.pth` 的編碼**：Python 3.11 以系統地區編碼（例如 cp950）讀 `.pth`。路徑有中文時要用同一種編碼寫；系統編碼表示不了的字，改用 8.3 短路徑。
- **批次檔**：`bootstrap-launcher.cmd` 只用 ASCII 並存成 CRLF（cmd.exe 以 OEM 編碼讀批次檔）。
- **`.iss`**：要存成 UTF-8 BOM 才能顯示中文；`[Code]` 裡也不能有以 `[` 開頭的行（會被當成區段標題）。
- **rusty-manga-image-translator**：上游的 wheel 裡有重複的 RECORD，安裝時要設 `UV_INSECURE_NO_ZIP_VALIDATION=1`。
