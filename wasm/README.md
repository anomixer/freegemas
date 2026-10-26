# Freegemas WebAssembly Port

English | [繁體中文](README-tw.md)

This directory contains the WebAssembly (WASM) build of Freegemas, allowing the original C++ SDL2 game to run directly in modern web browsers at 60 FPS without any plugins.

## Architecture

- **Engine**: The original C++ source (`src/`, `include/`) compiled directly to WebAssembly using [Emscripten](https://emscripten.org/).
- **Graphics**: Hardware-accelerated WebGL / SDL2 2D rendering at native 800×600 resolution with responsive CSS scaling.
- **Audio**: Web Audio API integration via SDL2 Mixer (`-s USE_OGG=1 -s USE_VORBIS=1`) supporting original background music and sound effects. Includes automatic audio context unlocking on first interaction.
- **Assets**: Embedded virtual filesystem via `--preload-file media@media` (images, fonts, audio).
- **Persistent Data**: Options and high scores are preserved using Emscripten's virtual filesystem (and browser local storage / IDBFS).
- **Self-Contained**: Includes a minimal single-header JsonCpp implementation in `vendor/` to eliminate external library dependencies during WASM compilation.

## How to Build

### Option 1: Automated GitHub Pages Deployment (Recommended)

This repository includes a GitHub Actions workflow in [`.github/workflows/deploy-wasm.yml`](../.github/workflows/deploy-wasm.yml). Whenever changes are pushed to `master`, GitHub Actions automatically:
1. Sets up the latest Emscripten SDK.
2. Compiles the game and packages the assets.
3. Deploys the result to GitHub Pages.

To enable GitHub Pages in your fork/repo:
- Go to **Settings** > **Pages**.
- Set **Source** to **GitHub Actions**.

### Option 2: Local Build

#### Prerequisites
- [Emscripten SDK (emsdk)](https://emscripten.org/docs/getting_started/downloads.html)
- CMake 3.10+
- Python 3

#### Build Commands

**Linux / macOS:**
```bash
# Activate Emscripten in your shell
source /path/to/emsdk/emsdk_env.sh

# Run the build script
./wasm/build.sh

# Start a local web server to test
python3 -m http.server 8080 -d wasm/dist
# Open http://localhost:8080 in your browser
```

**Windows (CMD / Batch):**
```cmd
:: Simply double-click or run build.bat:
wasm\build.bat

:: Or to only launch the local web server without rebuilding:
wasm\serve.bat
```

**Windows (PowerShell):**
```powershell
& "C:\path\to\emsdk\emsdk_env.ps1"
.\wasm\build.ps1
```

## Directory Structure

```
wasm/
├── CMakeLists.txt      # Emscripten CMake build definitions
├── build.bat           # Windows Batch build & preview script
├── serve.bat           # Standalone local HTTP server launcher
├── build.sh            # POSIX build script
├── build.ps1           # Windows PowerShell build script
├── shell.html          # Custom responsive HTML shell with glassmorphism UI
├── README.md           # Documentation (English)
├── README-tw.md        # Documentation (Traditional Chinese)
└── vendor/
    └── json/
        ├── json.h      # Self-contained JsonCpp header
        └── jsoncpp.cpp # Minimal parser implementation
```
