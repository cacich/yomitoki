# Yomitoki 瀏覽器插件

在 Chrome 看漫畫時按 `Alt+Shift+Y`，把畫面上看得到的內容交給本機的 Yomitoki 翻譯，並在側邊面板顯示譯圖。

## 安裝（v0.1 不上架商店）

1. 先啟動 Yomitoki：`yomitoki serve`（插件只連到 `http://127.0.0.1:8765`）。
2. Chrome 網址列輸入 `chrome://extensions`。
3. 打開右上角的「開發人員模式」。
4. 按「載入未封裝項目」，選這個 `extension` 資料夾。
5. 點工具列的拼圖圖示，把 Yomitoki 釘選到工具列（方便打開側邊面板）。

快捷鍵可以在 `chrome://extensions/shortcuts` 修改。如果 `Alt+Shift+Y` 跟其他插件衝突，Chrome 會讓它保持空白，這時到這裡設定一個就好。

## 使用

1. 點工具列上的 Yomitoki 圖示打開側邊面板，選「作品」與「話數」。
   - 不選作品：只翻這一張，不會存起來。
   - 選了作品：截圖會存進那一話，之後可以在 Yomitoki 裡重新翻譯、閱讀。
2. 選擇按下快捷鍵時要做什麼：
   - **馬上翻譯**：每按一次就翻這一頁，側邊面板直接顯示譯圖。按住「按住看原文」可以對照原文。
   - **只存截圖**：一頁一頁存起來，整話截完後到 Yomitoki 按「翻譯這一話」。整話一起翻，前後文比較連貫，也比較省額度。
3. 讓一頁完整出現在畫面上，按 `Alt+Shift+Y`。截圖前把視窗開大，對話框裡的小字會比較清楚。

## 做什麼、不做什麼

- 只用 Chrome 的 `captureVisibleTab` 擷取畫面上看得到的內容，跟手動截圖是同一件事。
- 不下載、不攔截、不讀取網頁裡的圖片，也沒有任何針對特定網站的程式碼。
- 截圖一律由你按鍵觸發，不會自動翻頁或自動捲動。
- 權限：`activeTab`（只有按快捷鍵或點圖示的那一刻能截圖）、`sidePanel`、`storage`，以及連到本機 `127.0.0.1:8765`。

## 開發

- 程式是原生 JavaScript（ES modules），不需要建置。
- `tokens.css` 與 `icons/` 是從 `ui/` 和 `assets/` 複製來的；改過設計 token 或圖示後，執行 `python scripts/sync-shared.py`。
- 測試：`node --test extension/lib.test.mjs`，以及 `pytest tests/test_extension.py`（檢查權限、使用界線、語系檔與同步的檔案）。
- 改了程式之後，到 `chrome://extensions` 按 Yomitoki 卡片上的重新整理圖示。
