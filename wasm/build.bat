@echo off
setlocal enabledelayedexpansion

title Building Freegemas WebAssembly

echo ========================================================
echo       Freegemas WebAssembly Build Script (Windows)
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "BUILD_DIR=%SCRIPT_DIR%build"
set "DIST_DIR=%SCRIPT_DIR%dist"

:: 1. Check if Emscripten is already in PATH
where emcmake >nul 2>nul
if %errorlevel% equ 0 goto :emscripten_ready

:: 2. Search common emsdk installation paths
if defined EMSDK (
    if exist "%EMSDK%\emsdk_env.bat" (
        echo [INFO] Found emsdk from %%EMSDK%% environment variable.
        call "%EMSDK%\emsdk_env.bat"
        goto :emscripten_ready
    )
)

if exist "C:\dev\emsdk\emsdk_env.bat" (
    echo [INFO] Found emsdk at C:\dev\emsdk
    call "C:\dev\emsdk\emsdk_env.bat"
    goto :emscripten_ready
)

if exist "C:\emsdk\emsdk_env.bat" (
    echo [INFO] Found emsdk at C:\emsdk
    call "C:\emsdk\emsdk_env.bat"
    goto :emscripten_ready
)

if exist "%USERPROFILE%\emsdk\emsdk_env.bat" (
    echo [INFO] Found emsdk at %USERPROFILE%\emsdk
    call "%USERPROFILE%\emsdk\emsdk_env.bat"
    goto :emscripten_ready
)

echo [ERROR] Emscripten SDK (emsdk) not found in PATH or standard paths!
echo.
echo Please install emsdk or run emsdk_env.bat first:
echo   1. git clone https://github.com/emscripten-core/emsdk.git C:\dev\emsdk
echo   2. cd C:\dev\emsdk
echo   3. emsdk install latest
echo   4. emsdk activate latest
echo.
pause
exit /b 1

:emscripten_ready
echo [INFO] Emscripten environment is ready.
echo.

:: 3. Prepare directories
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

cd /d "%BUILD_DIR%"

:: 4. Check for Ninja
set "CMAKE_GEN="
where ninja >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Ninja build tool detected, using Ninja generator.
    set "CMAKE_GEN=-G Ninja"
)

:: 5. Run emcmake and compile
echo [INFO] Configuring CMake with Emscripten...
call emcmake cmake "%SCRIPT_DIR%" %CMAKE_GEN%
if %errorlevel% neq 0 (
    echo [ERROR] CMake configuration failed!
    pause
    exit /b %errorlevel%
)

echo.
echo [INFO] Compiling WebAssembly binary...
call cmake --build . --parallel 4
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b %errorlevel%
)

:: 6. Copy output to dist/
echo.
echo [INFO] Copying web assets to %DIST_DIR%...
copy /y index.html "%DIST_DIR%\" >nul
copy /y index.js "%DIST_DIR%\" >nul
copy /y index.wasm "%DIST_DIR%\" >nul
copy /y index.data "%DIST_DIR%\" >nul
if exist "%SCRIPT_DIR%logo.png" copy /y "%SCRIPT_DIR%logo.png" "%DIST_DIR%\" >nul
type nul > "%DIST_DIR%\.nojekyll"

echo.
echo ========================================================
echo       Build Succeeded! Outputs in wasm\dist
echo ========================================================
echo.

:: 7. Optional local preview server
echo Starting local preview server at http://localhost:8080 ...
echo (Press Ctrl+C to stop the server)
echo.

start "" http://localhost:8080
python -m http.server 8080 -d "%DIST_DIR%"
