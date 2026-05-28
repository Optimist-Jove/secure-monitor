# Deploy Secure Monitor for all users on a PC (run as Administrator)
# Usage: Right-click -> Run with PowerShell (as Admin)

param(
    [string]$AppRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$SkipPythonCheck
)

$ErrorActionPreference = 'Stop'

function Test-Admin {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-File `"$PSCommandPath`""
    exit
}

Write-Host "=== Secure Monitor installer ===" -ForegroundColor Cyan

# 1) Machine-wide audit policy
Write-Host "Configuring audit policy..."
auditpol /set /subcategory:"Logon" /failure:enable | Out-Null
auditpol /set /subcategory:"Other Logon/Logoff Events" /success:enable /failure:enable | Out-Null

# 2) Run per-user fix for logged-on user
$fixScript = Join-Path $AppRoot "scripts\Fix-SecurityLog-Admin.ps1"
if (Test-Path $fixScript) {
    Write-Host "Running user setup script..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $fixScript
}

Write-Host ""
Write-Host "For each user account on this PC:" -ForegroundColor Yellow
Write-Host "  1. Log in as that user"
Write-Host "  2. Run the app once (completes first-run + UAC if needed)"
Write-Host "  3. Or run: $fixScript"
Write-Host ""
Write-Host "Python app path: $AppRoot\secure_monitor_daemon\secure_monitor_daemon.py"
Write-Host "Install complete." -ForegroundColor Green
Read-Host "Press Enter"
