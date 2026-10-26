# Freegemas WebAssembly build script for Windows (PowerShell)
# Requires Emscripten SDK activated in environment (emsdk_env.ps1)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $scriptDir "build"
$distDir = Join-Path $scriptDir "dist"

Write-Host "=== Building Freegemas WebAssembly ===" -ForegroundColor Cyan

if (-not (Get-Command "emcmake" -ErrorAction SilentlyContinue)) {
    Write-Error "emcmake not found! Please run 'emsdk_env.ps1' or add Emscripten to your PATH."
}

if (-not (Test-Path $buildDir)) { New-Item -ItemType Directory -Path $buildDir | Out-Null }
if (-not (Test-Path $distDir)) { New-Item -ItemType Directory -Path $distDir | Out-Null }

Set-Location $buildDir
emcmake cmake $scriptDir
cmake --build . --parallel 4

Copy-Item "index.html", "index.js", "index.wasm", "index.data" -Destination $distDir -Force

Write-Host "=== Build Complete! Outputs in $distDir ===" -ForegroundColor Green
Write-Host "To preview locally: python -m http.server 8080 -d $distDir" -ForegroundColor Yellow
