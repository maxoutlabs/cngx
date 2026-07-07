#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
& (Join-Path $PSScriptRoot "install_ttyd_msvc.ps1")

$tools = Join-Path $Root ".vhs-tools"
$env:Path = "$tools;" + $env:Path

foreach ($bin in @("vhs", "ffmpeg")) {
    if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) {
        throw "Missing $bin on PATH. Install via winget (charmbracelet.vhs, Gyan.FFmpeg)."
    }
}

Set-Location $Root
pip install -q -e .
Write-Host "Recording docs/assets/quickstart.gif ..."
vhs scripts/demo/quickstart.tape

$gif = Join-Path $Root "docs/assets/quickstart.gif"
$size = (Get-Item $gif).Length
Write-Host "Wrote $gif ($([math]::Round($size / 1KB, 1)) KB)"
