"""Windows Security log access and audit policy helpers."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from smd.logging_setup import log_message


@dataclass
class SecurityLogStatus:
    can_read_log: bool
    audit_logon_failure: bool
    audit_logon_success_other: bool
    sample_4625: bool
    sample_4800: bool
    error: str
    detail: str

    @property
    def ready_for_monitoring(self) -> bool:
        """True when we can read the log (events may still need audit + failed login test)."""
        return self.can_read_log

    @property
    def audit_configured(self) -> bool:
        return self.audit_logon_failure and self.audit_logon_success_other


def _powershell(script: str, timeout: int = 45) -> tuple[int, str, str]:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def diagnose_security_log() -> SecurityLogStatus:
    script = r"""
$ErrorActionPreference = 'Stop'
$result = @{
  can_read_log = $false
  audit_logon_failure = $false
  audit_logon_success_other = $false
  sample_4625 = $false
  sample_4800 = $false
  error = ''
  detail = ''
}
try {
  $null = Get-WinEvent -LogName Security -MaxEvents 1 -ErrorAction Stop
  $result.can_read_log = $true
  $result.detail = 'Can read Security log.'
} catch {
  $result.error = $_.Exception.Message
  $result.detail = 'Cannot read Security log. Enable auditing and grant access (see Fix steps).'
}

try {
  $logon = auditpol /get /subcategory:"Logon" 2>&1 | Out-String
  if ($logon -match '0x00000522|privilege is not held') {
    $result.detail += ' Run Fix-SecurityLog-Admin.ps1 as Administrator to set audit policy.'
  } elseif ($logon -match 'Failure\s+Enabled') { $result.audit_logon_failure = $true }
} catch {}

try {
  $other = auditpol /get /subcategory:"Other Logon/Logoff Events" 2>&1 | Out-String
  if ($other -match 'Success\s+Enabled') { $result.audit_logon_success_other = $true }
} catch {}

if ($result.can_read_log) {
  try {
    $e = Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 1 -EA SilentlyContinue
    if ($e) { $result.sample_4625 = $true }
  } catch {}
  try {
    $e = Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4800} -MaxEvents 1 -EA SilentlyContinue
    if ($e) { $result.sample_4800 = $true }
  } catch {}
}

$result | ConvertTo-Json -Compress
"""
    code, out, err = _powershell(script)
    if code != 0 and not out:
        return SecurityLogStatus(
            can_read_log=False,
            audit_logon_failure=False,
            audit_logon_success_other=False,
            sample_4625=False,
            sample_4800=False,
            error=err or "PowerShell failed",
            detail="Could not run security diagnostic.",
        )
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return SecurityLogStatus(
            can_read_log=False,
            audit_logon_failure=False,
            audit_logon_success_other=False,
            sample_4625=False,
            sample_4800=False,
            error=out or err,
            detail="Diagnostic parse error.",
        )
    return SecurityLogStatus(
        can_read_log=bool(data.get("can_read_log")),
        audit_logon_failure=bool(data.get("audit_logon_failure")),
        audit_logon_success_other=bool(data.get("audit_logon_success_other")),
        sample_4625=bool(data.get("sample_4625")),
        sample_4800=bool(data.get("sample_4800")),
        error=str(data.get("error") or ""),
        detail=str(data.get("detail") or ""),
    )


def _bundled_resource_root() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_admin_fix_script_path() -> Path:
    import sys

    from smd.paths import CONFIG_DIR

    root = _bundled_resource_root()
    candidates = [
        CONFIG_DIR / "Fix-SecurityLog-Admin.ps1",
        root / "smd" / "resources" / "Fix-SecurityLog-Admin.ps1",
        Path(__file__).resolve().parent / "resources" / "Fix-SecurityLog-Admin.ps1",
    ]
    if getattr(sys, "frozen", False):
        candidates.insert(0, Path(sys.executable).parent / "scripts" / "Fix-SecurityLog-Admin.ps1")
    else:
        candidates.append(
            Path(__file__).resolve().parent.parent.parent / "scripts" / "Fix-SecurityLog-Admin.ps1"
        )
    for src in candidates:
        if src.exists():
            return src
    return CONFIG_DIR / "Fix-SecurityLog-Admin.ps1"


def launch_admin_fix_script() -> Path:
    """Copy fix script to Desktop and launch elevated via UAC."""
    import shutil

    from smd.win_elevate import launch_elevated_powershell_script

    src = get_admin_fix_script_path()
    desktop = (Path.home() / "Desktop" / "SecureMonitor-Fix-SecurityLog.ps1").resolve()
    if src.exists():
        shutil.copy(src, desktop)
    else:
        bundled = Path(__file__).resolve().parent / "resources" / "Fix-SecurityLog-Admin.ps1"
        if bundled.exists():
            shutil.copy(bundled, desktop)
        else:
            desktop.write_text(
                "# Script missing. Reinstall Secure Monitor.\n",
                encoding="utf-8",
            )
    if not launch_elevated_powershell_script(desktop):
        log_message(f"Could not launch elevated setup script: {desktop}")
    return desktop


def enable_audit_policy_elevated() -> None:
    """Launch elevated PowerShell to enable auditing for 4625 and 4800."""
    from smd.paths import CONFIG_DIR
    from smd.win_elevate import launch_elevated_powershell_script

    script_path = (CONFIG_DIR / "enable_audit.ps1").resolve()
    script_path.write_text(
        """
Write-Host "Enabling audit policy for failed logon (4625) and lock (4800)..."
auditpol /set /subcategory:"Logon" /failure:enable
auditpol /set /subcategory:"Other Logon/Logoff Events" /success:enable /failure:enable
Write-Host ""
Write-Host "--- Logon ---"
auditpol /get /subcategory:"Logon"
Write-Host ""
Write-Host "--- Other Logon/Logoff Events ---"
auditpol /get /subcategory:"Other Logon/Logoff Events"
Write-Host ""
Write-Host "Done. Close this window and click Re-check in Secure Monitor."
pause
""".strip(),
        encoding="utf-8",
    )
    launch_elevated_powershell_script(script_path)


def grant_event_log_readers_hint() -> str:
    desktop = Path.home() / "Desktop" / "SecureMonitor-Fix-SecurityLog.ps1"
    return (
        "RECOMMENDED — one-shot fix (as Administrator):\n\n"
        f"  1. Use button 'Run full fix (Admin)' in Permissions\n"
        f"     OR right-click this file → Run with PowerShell:\n"
        f"        {desktop}\n\n"
        "  2. Approve UAC, wait for SUCCESS messages\n"
        "  3. Sign out and sign back in\n"
        "  4. Re-check Permissions in Secure Monitor\n\n"
        "Alternative: Controls → check 'Run worker elevated' → Enable startup again."
    )


def format_security_status(status: SecurityLogStatus) -> str:
    lines = [
        f"Read Security log: {'YES' if status.can_read_log else 'NO'}",
        f"Audit failed logon (4625): {'ON' if status.audit_logon_failure else 'OFF'}",
        f"Audit lock/unlock (4800): {'ON' if status.audit_logon_success_other else 'OFF'}",
    ]
    if status.can_read_log:
        lines.append(f"Past 4625 events in log: {'yes' if status.sample_4625 else 'none yet'}")
        lines.append(f"Past 4800 events in log: {'yes' if status.sample_4800 else 'none yet'}")
    if status.error:
        lines.append(f"Error: {status.error[:200]}")
    return "\n".join(lines)
