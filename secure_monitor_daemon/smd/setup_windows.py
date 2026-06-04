"""Automated Windows setup so end users avoid manual Security log troubleshooting."""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from smd.config import load_config, save_config
from smd.logging_setup import log_message
from smd.windows_security import diagnose_security_log, get_admin_fix_script_path, launch_admin_fix_script

_MARKER = Path.home() / ".secure_monitor" / "windows_setup.done"
_RESOURCE_SCRIPT = Path(__file__).resolve().parent / "resources" / "Fix-SecurityLog-Admin.ps1"


def ensure_fix_script_available() -> Path:
    """Copy bundled fix script to config dir and Desktop."""
    from smd.paths import CONFIG_DIR

    dest = CONFIG_DIR / "Fix-SecurityLog-Admin.ps1"
    src = get_admin_fix_script_path()
    if not src.exists() and _RESOURCE_SCRIPT.exists():
        src = _RESOURCE_SCRIPT
    if src.exists():
        shutil.copy(src, dest)
        desktop = Path.home() / "Desktop" / "SecureMonitor-Fix-SecurityLog.ps1"
        shutil.copy(src, desktop)
        return desktop
    return dest


def is_windows_setup_complete() -> bool:
    cfg = load_config()
    return bool(cfg.get("windows_setup_complete")) or _MARKER.exists()


def apply_windows_defaults() -> None:
    """Defaults for new Windows installs — elevated worker reads Security log."""
    if platform.system() != "Windows":
        return
    cfg = load_config()
    if "run_worker_elevated" not in cfg or cfg.get("schema_version", 0) < 3:
        cfg["run_worker_elevated"] = True
    cfg["schema_version"] = 3
    save_config(cfg)


def mark_windows_setup_complete() -> None:
    cfg = load_config()
    cfg["windows_setup_complete"] = True
    cfg["run_worker_elevated"] = True
    save_config(cfg)
    _MARKER.parent.mkdir(parents=True, exist_ok=True)
    _MARKER.write_text("", encoding="utf-8")


def is_security_ready() -> bool:
    """
    Monitoring can work if:
    - This user can read Security log + audit on, OR
    - One-time setup ran and worker uses elevation (Task Scheduler).
    """
    if platform.system() != "Windows":
        return True
    status = diagnose_security_log()
    if status.can_read_log and status.audit_configured:
        return True
    cfg = load_config()
    if cfg.get("run_worker_elevated") and is_windows_setup_complete():
        return True
    return False


def is_security_setup_in_progress() -> bool:
    """
    Check if Windows setup was started but not completed.
    This helps detect interrupted setups that cause persistent 'MISSING' status.
    """
    if platform.system() != "Windows":
        return False
    cfg = load_config()
    # If elevated mode is enabled but setup not marked complete, setup is in progress
    return bool(cfg.get("run_worker_elevated")) and not is_windows_setup_complete()


def recovery_mark_setup_complete() -> None:
    """
    Force-mark setup as complete after user has run the admin fix script.
    This is used for recovery when setup gets stuck in 'MISSING' state.
    """
    mark_windows_setup_complete()
    log_message("Windows setup marked complete (recovery mode)")


def run_admin_setup_script() -> Path:
    ensure_fix_script_available()
    return launch_admin_fix_script()


def run_interactive_setup(parent) -> bool:
    """
    First-run flow for Windows. Returns True when setup is acceptable to continue.
    """
    import tkinter as tk
    from tkinter import messagebox

    if platform.system() != "Windows":
        return True

    apply_windows_defaults()

    if is_security_ready():
        mark_windows_setup_complete()
        return True

    intro = (
        "Secure Monitor needs a one-time Windows setup (Administrator).\n\n"
        "This will:\n"
        "  • Turn on audit policy for wrong-password (4625) and lock (4800)\n"
        "  • Add you to Event Log Readers (or use elevated background task)\n\n"
        "You will see a UAC prompt — choose Yes.\n\n"
        "Run setup now?"
    )
    if not messagebox.askyesno("Windows setup (one time)", intro, parent=parent):
        if messagebox.askyesno(
            "Skip setup?",
            "Without setup, failed-login detection will NOT work.\n\n"
            "Continue anyway?",
            parent=parent,
        ):
            return False
        return False

    run_admin_setup_script()
    messagebox.showinfo(
        "Windows setup",
        "1. Approve the UAC prompt\n"
        "2. Wait for 'Setup complete' in the blue window\n"
        "3. Sign out and sign back in (recommended)\n"
        "4. Click OK here, then we enable elevated monitoring\n",
        parent=parent,
    )

    mark_windows_setup_complete()
    return True


def finalize_startup_after_setup() -> None:
    """Register elevated startup + spawn worker — call after first-run wizard."""
    from smd.process import is_worker_running, spawn_worker
    from smd.startup import add_to_startup

    if platform.system() != "Windows":
        return
    apply_windows_defaults()
    mark_windows_setup_complete()
    try:
        add_to_startup()
    except Exception as exc:
        log_message(f"Startup registration failed: {exc}")
    if not is_worker_running():
        spawn_worker()
