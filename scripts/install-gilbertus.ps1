<#
.SYNOPSIS
    Gilbertus Albans Desktop App Installer
.DESCRIPTION
    Downloads and installs the latest Gilbertus Albans desktop app from GitHub Releases.
.PARAMETER GitHubRepo
    GitHub repository in owner/repo format. Default: sebastianjablonski/personal-ai
.EXAMPLE
    .\install-gilbertus.ps1
#>
param(
    [string]$GitHubRepo = "sebastianjablonski/personal-ai"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Gilbertus Albans Desktop App Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Find latest release
Write-Host "[1/4] Szukam najnowszej wersji..." -ForegroundColor Yellow
try {
    $releases = Invoke-RestMethod "https://api.github.com/repos/$GitHubRepo/releases"
    $release = $releases | Where-Object { $_.tag_name -like "v*" -and $_.tag_name -notlike "omnius-v*" -and -not $_.prerelease } | Select-Object -First 1

    if (-not $release) {
        Write-Host "[FAIL] Nie znaleziono releasu Gilbertus." -ForegroundColor Red
        exit 1
    }

    Write-Host "       Znaleziono: $($release.tag_name)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Nie mozna polaczyc z GitHub: $_" -ForegroundColor Red
    exit 1
}

# 2. Find MSI asset
Write-Host "[2/4] Pobieram installer..." -ForegroundColor Yellow
$msi = $release.assets | Where-Object { $_.name -like "*.msi" } | Select-Object -First 1

if (-not $msi) {
    Write-Host "[FAIL] Nie znaleziono pliku MSI w relerasie." -ForegroundColor Red
    exit 1
}

$tempPath = Join-Path $env:TEMP "Gilbertus-setup.msi"

try {
    Invoke-WebRequest $msi.browser_download_url -OutFile $tempPath -UseBasicParsing
    Write-Host "       Pobrano: $($msi.name)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Blad pobierania: $_" -ForegroundColor Red
    exit 1
}

# 3. Install
Write-Host "[3/4] Instaluje Gilbertus Albans..." -ForegroundColor Yellow
try {
    $process = Start-Process msiexec.exe -ArgumentList "/i `"$tempPath`" /passive" -Wait -PassThru
    if ($process.ExitCode -eq 0) {
        Write-Host "       Zainstalowano pomyslnie!" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Instalacja zwrocila kod: $($process.ExitCode)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[FAIL] Blad instalacji: $_" -ForegroundColor Red
    exit 1
}

# 4. Cleanup and launch
Write-Host "[4/4] Uruchamiam Gilbertus Albans..." -ForegroundColor Yellow
Remove-Item $tempPath -ErrorAction SilentlyContinue

# Try to find and start Gilbertus
$gilbertusPath = Get-ChildItem "$env:ProgramFiles\Gilbertus Albans" -Filter "Gilbertus Albans.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($gilbertusPath) {
    Start-Process $gilbertusPath.FullName
} else {
    # Try Start Menu shortcut
    Start-Process "Gilbertus Albans" -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=== Gilbertus Albans zainstalowany! ===" -ForegroundColor Cyan
Write-Host "    Aplikacja desktopowa gotowa do uzycia." -ForegroundColor Gray
Write-Host ""
