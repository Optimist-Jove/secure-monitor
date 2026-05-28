import platform
import subprocess
from pathlib import Path

from smd.config import load_config, save_config
from smd.process import get_worker_command


def _launch_string() -> str:
    cmd = get_worker_command()
    parts = [f'"{c}"' if " " in c else c for c in cmd]
    return " ".join(parts)


def register_task_scheduler(*, elevated: bool = False) -> None:
    if platform.system() != "Windows":
        return
    launch = _launch_string()
    run_level = "HIGHEST" if elevated else "LIMITED"
    subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            "SecureMonitorWorker",
            "/TR",
            launch,
            "/SC",
            "ONLOGON",
            "/RL",
            run_level,
            "/F",
        ],
        check=False,
        capture_output=True,
    )
    subprocess.run(
        [
            "schtasks",
            "/Change",
            "/TN",
            "SecureMonitorWorker",
            "/ENABLE",
        ],
        check=False,
    )


def remove_task_scheduler() -> None:
    if platform.system() == "Windows":
        subprocess.run(["schtasks", "/Delete", "/TN", "SecureMonitorWorker", "/F"], check=False)


def register_linux_systemd_user() -> None:
    if platform.system() != "Linux":
        return
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    launch = _launch_string()
    unit = f"""[Unit]
Description=Secure Monitor Worker
After=default.target

[Service]
Type=simple
ExecStart={launch}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""
    (unit_dir / "secure-monitor.service").write_text(unit, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "secure-monitor.service"], check=False)


def remove_linux_systemd_user() -> None:
    if platform.system() != "Linux":
        return
    subprocess.run(["systemctl", "--user", "disable", "secure-monitor.service"], check=False)
    unit = Path.home() / ".config" / "systemd" / "user" / "secure-monitor.service"
    unit.unlink(missing_ok=True)


def add_to_startup() -> None:
    current_os = platform.system()
    launch = _launch_string()

    if current_os == "Windows":
        import winreg

        key = winreg.HKEY_CURRENT_USER
        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(key, path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, "SecureMonitorWorker", 0, winreg.REG_SZ, launch)
        register_task_scheduler(elevated=load_config().get("run_worker_elevated", False))

    elif current_os == "Darwin":
        cmd = get_worker_command()
        plist_args = "".join(f"<string>{a}</string>" for a in cmd)
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key><string>com.securemonitor.worker</string>
    <key>ProgramArguments</key>
    <array>{plist_args}</array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>
"""
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.securemonitor.worker.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist, encoding="utf-8")

    elif current_os == "Linux":
        autostart = Path.home() / ".config" / "autostart"
        autostart.mkdir(parents=True, exist_ok=True)
        desktop = f"""[Desktop Entry]
Type=Application
Exec={launch}
Hidden=true
NoDisplay=true
X-GNOME-Autostart-enabled=true
Name=Secure Monitor Worker
"""
        (autostart / "secure-monitor-worker.desktop").write_text(desktop, encoding="utf-8")
        register_linux_systemd_user()

    cfg = load_config()
    cfg["startup_enabled"] = True
    save_config(cfg)


def remove_from_startup() -> None:
    current_os = platform.system()
    if current_os == "Windows":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as reg_key:
                winreg.DeleteValue(reg_key, "SecureMonitorWorker")
        except OSError:
            pass
        remove_task_scheduler()

    elif current_os == "Darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / "com.securemonitor.worker.plist"
        plist.unlink(missing_ok=True)

    elif current_os == "Linux":
        desktop = Path.home() / ".config" / "autostart" / "secure-monitor-worker.desktop"
        desktop.unlink(missing_ok=True)
        remove_linux_systemd_user()

    cfg = load_config()
    cfg["startup_enabled"] = False
    save_config(cfg)
