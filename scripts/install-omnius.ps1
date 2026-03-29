<#
.SYNOPSIS
    Omnius Desktop App Installer
.DESCRIPTION
    Downloads and installs the latest Omnius desktop app from GitHub Releases.
.PARAMETER Tenant
    The tenant to configure (ref or reh). Default: ref
.PARAMETER GitHubRepo
    GitHub repository in owner/repo format. Default: sebastianjablonski/personal-ai
.EXAMPLE
    .\install-omnius.ps1
    .\install-omnius.ps1 -Tenant reh
#>
param(
    [ValidateSet("ref", "reh")]
    [string]$Tenant = "ref",

    [string]$GitHubRepo = "sebastianjablonski/personal-ai"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Omnius Desktop App Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Find latest release
Write-Host "[1/4] Szukam najnowszej wersji..." -ForegroundColor Yellow
try {
    $releases = Invoke-RestMethod "https://api.github.com/repos/$GitHubRepo/releases"
    $release = $releases | Where-Object { $_.tag_name -like "omnius-v*" -and -not $_.prerelease } | Select-Object -First 1

    if (-not $release) {
        Write-Host "[FAIL] Nie znaleziono releasu Omnius." -ForegroundColor Red
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

$tempPath = Join-Path $env:TEMP "Omnius-setup.msi"

try {
    Invoke-WebRequest $msi.browser_download_url -OutFile $tempPath -UseBasicParsing
    Write-Host "       Pobrano: $($msi.name)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Blad pobierania: $_" -ForegroundColor Red
    exit 1
}

# 3. Install
Write-Host "[3/4] Instaluje Omnius..." -ForegroundColor Yellow
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
Write-Host "[4/4] Uruchamiam Omnius..." -ForegroundColor Yellow
Remove-Item $tempPath -ErrorAction SilentlyContinue

# Try to find and start Omnius
$omniusPath = Get-ChildItem "$env:ProgramFiles\Omnius" -Filter "Omnius.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($omniusPath) {
    Start-Process $omniusPath.FullName
} else {
    # Try Start Menu shortcut
    Start-Process "Omnius" -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=== Omnius zainstalowany! ===" -ForegroundColor Cyan
Write-Host "    Przy pierwszym uruchomieniu podaj adres serwera i klucz API." -ForegroundColor Gray
Write-Host ""
