# Secure Monitor — Security Event Log Fix (Administrator Required)
# This script fixes persistent "MISSING" status for security event log access.
# Run as Administrator to: enable audit policy, add Event Log Readers group, and test.

#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

# Colors for output
$Success = 'Green'
$Warning = 'Yellow'
$Error = 'Red'
$Info = 'Cyan'

Write-Host ""
Write-Host "=== Secure Monitor — Security Event Log Fix ===" -ForegroundColor $Info
Write-Host "This script requires Administrator privileges." -ForegroundColor $Warning
Write-Host ""

# Verify Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor $Error
    Write-Host "Right-click PowerShell → Run as administrator" -ForegroundColor $Warning
    exit 1
}

Write-Host "[1/4] Checking current Security event log status..." -ForegroundColor $Info
Write-Host ""

# Step 1: Diagnose current status
$testRead = $false
try {
    $null = Get-WinEvent -LogName Security -MaxEvents 1 -ErrorAction Stop
    $testRead = $true
    Write-Host "✓ Can already read Security log" -ForegroundColor $Success
} catch {
    Write-Host "✗ Cannot read Security log yet (will fix)" -ForegroundColor $Warning
}

# Step 2: Enable audit policy
Write-Host ""
Write-Host "[2/4] Enabling audit policy..." -ForegroundColor $Info
Write-Host ""

$auditFailed = $false
$auditSucceeded = $false

try {
    Write-Host "  Setting: Failed logon (4625) → Enabled"
    auditpol /set /subcategory:"Logon" /failure:enable 2>&1 | Out-Null
    $auditSucceeded = $true
} catch {
    Write-Host "  ✗ Failed to enable 4625 audit" -ForegroundColor $Error
    $auditFailed = $true
}

try {
    Write-Host "  Setting: Lock/Unlock (4800/4801) → Enabled"
    auditpol /set /subcategory:"Other Logon/Logoff Events" /success:enable /failure:enable 2>&1 | Out-Null
} catch {
    Write-Host "  ✗ Failed to enable 4800/4801 audit" -ForegroundColor $Error
    $auditFailed = $true
}

if ($auditSucceeded) {
    Write-Host "✓ Audit policy configured" -ForegroundColor $Success
} else {
    Write-Host "✗ Audit policy configuration had issues" -ForegroundColor $Error
}

Write-Host ""
Write-Host "Audit policy status:" -ForegroundColor $Info
Write-Host ""
auditpol /get /subcategory:"Logon" 2>&1 | ForEach-Object { Write-Host "  $_" }
Write-Host ""
auditpol /get /subcategory:"Other Logon/Logoff Events" 2>&1 | ForEach-Object { Write-Host "  $_" }
Write-Host ""

# Step 3: Add Event Log Readers group (if not already accessible)
Write-Host "[3/4] Adding user to Event Log Readers group..." -ForegroundColor $Info
Write-Host ""

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$eventLogReadersExists = $false
$userInGroup = $false

try {
    $groupMembers = net localgroup "Event Log Readers" 2>&1
    $eventLogReadersExists = $true
    if ($groupMembers -match [regex]::Escape($currentUser)) {
        $userInGroup = $true
        Write-Host "✓ User '$currentUser' already in Event Log Readers" -ForegroundColor $Success
    } else {
        Write-Host "  Adding '$currentUser' to Event Log Readers..."
        net localgroup "Event Log Readers" "$currentUser" /add 2>&1 | Out-Null
        Write-Host "✓ User added to Event Log Readers" -ForegroundColor $Success
    }
} catch {
    Write-Host "✗ Could not manage Event Log Readers group: $_" -ForegroundColor $Error
}

Write-Host ""

# Step 4: Test security log access
Write-Host "[4/4] Testing Security event log access..." -ForegroundColor $Info
Write-Host ""

$canRead = $false
try {
    $event = Get-WinEvent -LogName Security -MaxEvents 1 -ErrorAction Stop
    $canRead = $true
    Write-Host "✓ Can read Security event log" -ForegroundColor $Success
    if ($event) {
        Write-Host "  Latest event ID: $($event.Id)" -ForegroundColor $Info
        Write-Host "  Time: $($event.TimeCreated)" -ForegroundColor $Info
    }
} catch {
    Write-Host "✗ Cannot read Security event log: $($_.Exception.Message)" -ForegroundColor $Error
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor $Warning
    Write-Host "  1. You may need to sign out and sign back in for group changes to take effect"
    Write-Host "  2. Restart the computer if needed"
    Write-Host "  3. Check that auditing is enabled (see above)"
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor $Info
Write-Host ""
if ($canRead -and $auditSucceeded) {
    Write-Host "✓ SUCCESS: All checks passed!" -ForegroundColor $Success
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor $Info
    Write-Host "  1. Sign out and sign back in to Windows"
    Write-Host "  2. Open Secure Monitor → Permissions → Re-check"
    Write-Host "  3. The 'Security event log' status should now show OK"
} else {
    Write-Host "⚠ Some checks incomplete — see details above" -ForegroundColor $Warning
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor $Info
    Write-Host "  1. Review any errors above"
    Write-Host "  2. Sign out and sign back in to apply group membership changes"
    Write-Host "  3. Run this script again if needed"
    Write-Host "  4. Contact support if issues persist"
}

Write-Host ""
Write-Host "Press Enter to close..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
