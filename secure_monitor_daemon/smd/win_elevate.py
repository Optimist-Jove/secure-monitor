"""Launch elevated processes on Windows without fragile PowerShell quoting."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def launch_elevated_powershell_script(script_path: Path) -> bool:
    """
    Run a .ps1 file as Administrator via UAC (ShellExecute runas).
    Returns True if launch was initiated successfully.
    """
    if platform.system() != "Windows":
        return False

    script = Path(script_path).resolve()
    if not script.exists():
        return False

    import ctypes

    # > 32 means ShellExecute succeeded (user may still cancel UAC)
    params = f'-NoProfile -ExecutionPolicy Bypass -File "{script}"'
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        "powershell.exe",
        params,
        None,
        1,  # SW_SHOWNORMAL
    )
    return int(result) > 32


def launch_elevated_powershell_command(command: str) -> bool:
    """Run an inline PowerShell command as Administrator."""
    if platform.system() != "Windows":
        return False
    import ctypes

    params = f'-NoProfile -ExecutionPolicy Bypass -Command "{command}"'
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "powershell.exe", params, None, 1
    )
    return int(result) > 32
