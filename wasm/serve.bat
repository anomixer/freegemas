@echo off
setlocal

set "DIST_DIR=%~dp0dist"

if not exist "%DIST_DIR%\index.html" (
    echo [ERROR] %DIST_DIR%\index.html not found!
    echo Please run build.bat first.
    pause
    exit /b 1
)

echo Starting local Freegemas server at http://localhost:8080 ...
echo (Press Ctrl+C to stop the server)
echo.

start "" http://localhost:8080
python -m http.server 8080 -d "%DIST_DIR%"
