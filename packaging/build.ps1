# Builds the Windows release zip. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

python -m PyInstaller (Join-Path $PSScriptRoot "tbh_macro.spec") `
    --noconfirm `
    --distpath (Join-Path $root "dist") `
    --workpath (Join-Path $root "build")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$out = Join-Path $root "dist\tbh-macro"
# Ship the EXAMPLE config as the live one — never the developer's config.py.
Copy-Item (Join-Path $root "config.example.py") (Join-Path $out "config.py") -Force
Copy-Item (Join-Path $PSScriptRoot "README-release.txt") (Join-Path $out "README.txt") -Force

$zip = Join-Path $root "dist\tbh-macro-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $out -DestinationPath $zip
Write-Host "Release zip: $zip"
