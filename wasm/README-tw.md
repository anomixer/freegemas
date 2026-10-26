# Freegemas WebAssembly 移植版

[English](README.md) | 繁體中文

本目錄包含 Freegemas 的 WebAssembly（WASM）建置設定，讓原版 C++ SDL2 遊戲能以 60 FPS 直接在現代瀏覽器中流暢運行，無需安裝任何外掛套件。

## 架構與特性

- **核心架構**：使用 [Emscripten](https://emscripten.org/) 直接將原版 C++ 原始碼（`src/`、`include/`）編譯為 WebAssembly。
- **畫面顯示**：硬體加速 WebGL / SDL2 2D 算繪，以原生 800×600 解析度渲染，並具備現代自適應響應式 CSS 縮放。
- **音訊支援**：透過 SDL2 Mixer 橋接 Web Audio API（`-s USE_OGG=1 -s USE_VORBIS=1`），完整支援原版背景音樂與 PCM 音效，並包含瀏覽器初次點擊自動解鎖音訊上下文機制。
- **資產打包**：使用 `--preload-file media@media` 將圖片、字型與音效直接封裝為虛擬檔案系統。
- **紀錄儲存**：設定與最高分透過虛擬檔案系統與瀏覽器 IDBFS 本地保存。
- **零外部依賴**：在 `vendor/` 中提供輕量化單檔 JsonCpp 實作，消除編譯 WASM 時對外部系統套件庫的依賴。

## 建置方式

### 方法一：GitHub Actions 自動部署至 GitHub Pages（推薦）

本專案已設定好 [`.github/workflows/deploy-wasm.yml`](../.github/workflows/deploy-wasm.yml)。只要推送至 `master` 分支，GitHub Actions 就會自動：
1. 下載並設定最新版 Emscripten SDK。
2. 自動編譯遊戲並打包資產。
3. 自動發布並更新至 GitHub Pages。

啟用 GitHub Pages 方式：
- 進入 GitHub 專案的 **Settings** > **Pages**。
- 將 **Source** 切換為 **GitHub Actions**。

### 方法二：本機建置

#### 前置需求
- [Emscripten SDK (emsdk)](https://emscripten.org/docs/getting_started/downloads.html)
- CMake 3.10 以上
- Python 3

#### 建置指令

**Linux / macOS：**
```bash
# 在 Shell 中啟用 Emscripten 環境變數
source /path/to/emsdk/emsdk_env.sh

# 執行建置腳本
./wasm/build.sh

# 啟動本機測試伺服器
python3 -m http.server 8080 -d wasm/dist
# 瀏覽器打開 http://localhost:8080 即可遊玩
```

**Windows（CMD / 批次檔）：**
```cmd
:: 直接雙擊或在終端機執行 build.bat：
wasm\build.bat

:: 若只需啟動本地測試伺服器（無需重新編譯）：
wasm\serve.bat
```

**Windows（PowerShell）：**
```powershell
& "C:\path\to\emsdk\emsdk_env.ps1"
.\wasm\build.ps1
```

## 目錄結構

```
wasm/
├── CMakeLists.txt      # Emscripten CMake 建置設定
├── build.bat           # Windows 批次檔建置與預覽腳本
├── serve.bat           # 獨立本機 HTTP 伺服器啟動腳本
├── build.sh            # POSIX 建置腳本
├── build.ps1           # Windows PowerShell 建置腳本
├── shell.html          # 現代毛玻璃質感的 HTML Shell 介面
├── README.md           # 英文說明文件
├── README-tw.md        # 繁體中文說明文件
└── vendor/
    └── json/
        ├── json.h      # 自給自足的 JsonCpp 標頭檔
        └── jsoncpp.cpp # 輕量化 JSON 解析器實作
```
