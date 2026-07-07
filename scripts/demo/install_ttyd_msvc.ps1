#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure MSVC-built ttyd is available on Windows 11 25H2+.

  Upstream winget ttyd (MinGW) fails ConPTY spawn (CreateProcessW error 123).
  See: https://github.com/tsl0922/ttyd/issues/1501
#>
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$Tools = Join-Path $Root ".vhs-tools"
$Marker = Join-Path $Tools "ttyd.exe"

if (Test-Path $Marker) {
    Write-Host "MSVC ttyd already present at $Tools"
    exit 0
}

New-Item -ItemType Directory -Force -Path $Tools | Out-Null
$zip = Join-Path $Tools "ttyd-msvc-win64.zip"
Write-Host "Downloading MSVC ttyd to $Tools ..."
gh release download 1.7.7-msvc1 --repo djdarcy/ttyd-msvc --pattern "ttyd-msvc-win64.zip" --dir $Tools --clobber
Expand-Archive -Force $zip -DestinationPath $Tools
Remove-Item $zip -Force
Write-Host "Installed $Marker"
