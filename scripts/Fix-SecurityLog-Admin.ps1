# Run as Administrator (right-click -> Run with PowerShell as Admin)
# Fixes Secure Monitor: audit policy for 4625/4800 + Event Log Readers group

$ErrorActionPreference = 'Stop'

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "Re-launching as Administrator..."
    Start-Process powershell.exe -Verb RunAs -ArgumentList (
        "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    )
    exit
}

Write-Host "=== Secure Monitor: Security log fix ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Enabling audit policy for failed logon (4625)..." -ForegroundColor Yellow
auditpol /set /subcategory:"Logon" /failure:enable
auditpol /set /subcategory:"Logon" /success:disable

Write-Host "[2/3] Enabling audit policy for lock/unlock (4800/4801)..." -ForegroundColor Yellow
auditpol /set /subcategory:"Other Logon/Logoff Events" /success:enable /failure:enable

Write-Host ""
Write-Host "Audit status:" -ForegroundColor Green
auditpol /get /subcategory:"Logon"
auditpol /get /subcategory:"Other Logon/Logoff Events"

Write-Host ""
Write-Host "[3/3] Granting Security log read access..." -ForegroundColor Yellow
$account = "$env:USERDOMAIN\$env:USERNAME"
try {
    & net localgroup "Event Log Readers" $account /add 2>&1 | Out-Host
    Write-Host "Added $account to Event Log Readers." -ForegroundColor Green
} catch {
    Write-Host "Note: $($_.Exception.Message)" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "Testing Security log read..." -ForegroundColor Yellow
try {
    $e = Get-WinEvent -LogName Security -MaxEvents 1 -ErrorAction Stop
    Write-Host "SUCCESS: Can read Security log (RecordId $($e.RecordId))." -ForegroundColor Green
} catch {
    Write-Host "Still cannot read: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Enable 'Run worker elevated' in the app, or sign out and back in after group change."
}

$markerDir = Join-Path $env:USERPROFILE ".secure_monitor"
$marker = Join-Path $markerDir "windows_setup.done"
New-Item -ItemType Directory -Force -Path $markerDir | Out-Null
Get-Date -Format o | Set-Content -Path $marker -Encoding UTF8

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "1. Sign out and sign back in (if Event Log Readers was added)"
Write-Host "2. Open Secure Monitor -> Permissions -> Re-check"
Write-Host "3. Enable 'Run worker elevated' is ON by default"
Write-Host "4. Enter a wrong password once to test 4625"
Write-Host ""
Read-Host "Press Enter to close"
