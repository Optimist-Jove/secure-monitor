# Build Secure Monitor EXE + Windows installer (with disclaimer)
# Requires: Python 3.10+, pip, PyInstaller. Optional: Inno Setup 6.

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$AppDir = Join-Path $Root "secure_monitor_daemon"
$DistExe = Join-Path $AppDir "dist\SecureMonitor.exe"
$InstallerOut = Join-Path $Root "installer\output"

Write-Host "=== Secure Monitor build ===" -ForegroundColor Cyan

Write-Host "[1/4] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r (Join-Path $Root "requirements.txt") pyinstaller --quiet

Write-Host "[2/4] Building EXE with PyInstaller..." -ForegroundColor Yellow
Push-Location $AppDir
pyinstaller Daemon.spec --noconfirm --clean
Pop-Location

if (-not (Test-Path $DistExe)) {
    Write-Error "Build failed: $DistExe not found"
}

Write-Host "  EXE: $DistExe" -ForegroundColor Green
(Get-Item $DistExe).Length / 1MB | ForEach-Object { Write-Host ("  Size: {0:N1} MB" -f $_) }

Write-Host "[3/4] Building installer (Inno Setup)..." -ForegroundColor Yellow
$IsccPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "  Inno Setup not found. Install from: https://jrsoftware.org/isinfo.php" -ForegroundColor DarkYellow
    Write-Host "  Then run: `"`$Iscc`" `"$(Join-Path $Root 'installer\SecureMonitor.iss')`"" -ForegroundColor DarkYellow
    Write-Host ""
    Write-Host "EXE ready without installer: $DistExe" -ForegroundColor Green
    exit 0
}

New-Item -ItemType Directory -Force -Path $InstallerOut | Out-Null
& $Iscc (Join-Path $Root "installer\SecureMonitor.iss")
$Setup = Get-ChildItem $InstallerOut -Filter "SecureMonitor-Setup*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

Write-Host "[4/4] Done." -ForegroundColor Green
if ($Setup) {
    Write-Host "  Installer: $($Setup.FullName)" -ForegroundColor Green
} else {
    Write-Host "  Check installer\output\" -ForegroundColor Yellow
}
