param([string]$PlayerSource = 'C:\dev\veramusic\tools')
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$outputDirectory = Join-Path $workspace 'llvm\build'
$compilerSetup = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
if (!(Test-Path -LiteralPath $compilerSetup)) { throw "Missing compiler setup: $compilerSetup" }
if (!(Test-Path -LiteralPath (Join-Path $PlayerSource 'psgplay.c'))) { throw 'Missing psgplay.c' }
$source = Join-Path $PSScriptRoot 'psgplay_compare.c'
$executable = Join-Path $outputDirectory 'psgplay_compare.exe'
$object = Join-Path $outputDirectory 'psgplay_compare.obj'
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$command = 'call "{0}" >nul && cl /nologo /O2 /MT /W3 /I"{1}" "{2}" /Fo"{3}" /link winmm.lib /out:"{4}"' -f $compilerSetup, $PlayerSource, $source, $object, $executable
& $env:ComSpec /d /s /c $command
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic player build failed' }
Write-Output $executable
