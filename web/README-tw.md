# Freegemas 瀏覽器入口頁

這個目錄建置 Freegemas 的 GitHub Pages 入口頁，以及由本倉庫提供的兩個
瀏覽器版本：

- **Native WebAssembly**：原始 C++/SDL2 遊戲以 Emscripten 編譯，來源在
  [`wasm/`](../wasm/)。
- **Commander X16**：65C02/VERA 連接埠，由官方 X16Community WebAssembly
  x16emu r49 開機，來源在 [`x16/web/`](../x16/web/)。

入口頁也連到兩個外部瀏覽器模擬器：

- **Apple //e + VERA**：[Apple2TS](https://apple2ts.com/) 串流
  [`vera/freegemas.hdv`](../vera/freegemas.hdv)。
- **Apple IIgs**：[a2gsemu-ia](https://a2gsemu-ia.pages.dev/) 從本倉庫開機
  IIgs 版本。

## 目錄

| 路徑 | 用途 |
| --- | --- |
| `index.html` | 入口頁與四張平台卡片 |
| `assets/freegemas-logo.png` | hero 區使用的 Freegemas logo |
| `assets/gems/` | hero 區的七顆寶石圖示 |
| `build-site.mjs` | 把入口頁、`wasm/dist/`、`x16/web/dist/` 組成 `_site/` |
| `_site/` | 產出目錄，已 gitignore |

## 建置

需要 Node.js 20 以上。這個腳本只負責組合，不會編譯兩個連接埠。

```powershell
# 1. Native WebAssembly（PATH 需要 Emscripten SDK）
.\wasm\build.ps1

# 2. Commander X16 瀏覽器版（需要 Node 20+；會下載固定版本的 r49 emulator）
node .\x16\web\build.mjs

# 3. 入口頁
node .\web\build-site.mjs
```

Linux/macOS 請改用 `./wasm/build.sh`，再執行同一個 `build-site.mjs`。
若任一連接埠尚未建置，`build-site.mjs` 會直接報錯並提示指令。

請用 HTTP 伺服器預覽，不要直接開 `file://`：

```powershell
python -m http.server 8123 --directory C:\dev\freegemas\web\_site
# <http://127.0.0.1:8123/>
```

## 部署

[`.github/workflows/deploy-wasm.yml`](../.github/workflows/deploy-wasm.yml)
會在 push 到 `master` 時建置 WASM、X16 與入口頁，然後把 `web/_site` 發佈到
GitHub Pages。倉庫設定裡需將 Pages 的 Source 設為 **GitHub Actions**。

公開網址：

- 入口頁：<https://anomixer.github.io/freegemas/>
- Native WebAssembly：<https://anomixer.github.io/freegemas/wasm/>
- Commander X16：<https://anomixer.github.io/freegemas/x16/>

A2VERA 與 IIgs 卡片直接使用外部模擬器網址，因此不需要在 `web/_site` 內
複製這兩個版本。

## 驗證狀態

入口頁版面與組合流程屬於本地靜態網站工作。Native WebAssembly 與 X16
瀏覽器版由 GitHub Actions 建置，不把成品 vendored 進倉庫。A2VERA 與 IIgs
是由各自的外部瀏覽器模擬器提供，本頁只負責連結；網站建置本身不會執行
這兩個模擬器的完整遊玩測試。這裡也不代表已完成真實硬體驗證。
