# Secure Monitor — one-time Windows setup (runs elevated)
$ErrorActionPreference = 'Stop'

function Test-IsAdmin {
    $p = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList (
        "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    )
    exit
}

$markerDir = Join-Path $env:USERPROFILE ".secure_monitor"
$marker = Join-Path $markerDir "windows_setup.done"
New-Item -ItemType Directory -Force -Path $markerDir | Out-Null

Write-Host "=== Secure Monitor: Windows setup ===" -ForegroundColor Cyan

auditpol /set /subcategory:"Logon" /failure:enable | Out-Null
auditpol /set /subcategory:"Other Logon/Logoff Events" /success:enable /failure:enable | Out-Null

$account = "$env:USERDOMAIN\$env:USERNAME"
net localgroup "Event Log Readers" $account /add 2>$null

$readOk = $false
try {
    Get-WinEvent -LogName Security -MaxEvents 1 -ErrorAction Stop | Out-Null
    $readOk = $true
} catch {}

if ($readOk) {
    Write-Host "SUCCESS: Security log is readable." -ForegroundColor Green
} else {
    Write-Host "NOTE: GUI user still cannot read Security log." -ForegroundColor Yellow
    Write-Host "The app will run its worker elevated via Task Scheduler." -ForegroundColor Yellow
}

Get-Date -Format o | Set-Content -Path $marker -Encoding UTF8
Write-Host ""
Write-Host "Setup complete. You may close this window." -ForegroundColor Green
Read-Host "Press Enter"
