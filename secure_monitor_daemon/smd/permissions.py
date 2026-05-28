"""Permissions checks and setup wizard."""
import platform
import subprocess
import webbrowser
from dataclasses import dataclass

import keyring
import tkinter as tk
from tkinter import messagebox, ttk

from smd.alerts import send_alert
from smd.logging_setup import log_message
from smd.paths import CONFIG_DIR, KEYRING_SERVICE

try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None


@dataclass
class PermissionItem:
    id: str
    title: str
    description: str
    granted: bool
    required: bool
    action_label: str = "Open settings"
    settings_target: str = ""
    extra_detail: str = ""


def open_system_target(target: str) -> bool:
    if not target:
        return False
    system = platform.system()
    try:
        if system == "Windows":
            import os
            os.startfile(target)  # noqa: S606
            return True
        if system == "Darwin":
            subprocess.run(["open", target], check=False)
            return True
        if target.startswith("http"):
            webbrowser.open(target)
            return True
        subprocess.run(["xdg-open", target], check=False)
        return True
    except OSError as exc:
        log_message(f"Could not open '{target}': {exc}")
        return False


def _settings_targets() -> dict[str, str]:
    system = platform.system()
    if system == "Windows":
        return {
            "camera": "ms-settings:privacy-webcam",
            "notifications": "ms-settings:notifications",
            "security_events": "eventvwr.msc",
            "audit": "gpedit.msc",
            "keyring": "ms-settings:credentialmanager",
            "storage": str(CONFIG_DIR),
        }
    if system == "Darwin":
        return {
            "camera": "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
            "notifications": "x-apple.systempreferences:com.apple.preference.notifications",
            "security_events": "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
            "keyring": "x-apple.systempreferences:com.apple.preference.security",
            "storage": str(CONFIG_DIR),
        }
    return {
        "camera": "https://wiki.archlinux.org/title/Webcam_setup",
        "notifications": "https://wiki.archlinux.org/title/Desktop_notifications",
        "security_events": "https://www.freedesktop.org/software/systemd/man/journalctl.html",
        "keyring": "https://wiki.archlinux.org/title/GNOME/Keyring",
        "storage": str(CONFIG_DIR),
    }


def _check_camera() -> bool:
    from smd.camera_util import open_camera, read_frame

    cap = open_camera(0)
    if not cap.isOpened():
        return False
    try:
        ret, _ = read_frame(cap, warmup_frames=1)
        return bool(ret)
    finally:
        cap.release()


def _check_notifications() -> bool:
    if not plyer_notification:
        return False
    try:
        plyer_notification.notify(
            title="Secure Monitor", message="Test", app_name="Secure Monitor", timeout=3
        )
        return True
    except Exception:
        return False


def _check_keyring() -> bool:
    try:
        keyring.set_password(KEYRING_SERVICE, "_probe", "ok")
        keyring.delete_password(KEYRING_SERVICE, "_probe")
        return True
    except Exception:
        return False


def _check_storage() -> bool:
    probe = CONFIG_DIR / ".write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _windows_security_item() -> PermissionItem:
    from smd.setup_windows import is_security_ready, is_windows_setup_complete
    from smd.windows_security import diagnose_security_log, format_security_status
    from smd.config import load_config

    status = diagnose_security_log()
    cfg = load_config()
    granted = is_security_ready()

    parts = [
        "Failed logon (4625) and lock (4800) require one-time Windows setup (Administrator).",
    ]
    if granted and cfg.get("run_worker_elevated") and is_windows_setup_complete():
        parts.append("Setup complete — background worker runs with required privileges.")
    elif granted:
        parts.append("Security log is readable and audit policy is configured.")
    else:
        parts.append("Click 'Run full fix (Admin)' or complete first-run setup.")
    if not status.audit_configured:
        parts.append("Audit policy is OFF until Admin setup runs.")
    if not status.can_read_log and not is_windows_setup_complete():
        parts.append("Run the one-time Admin fix (UAC prompt).")
    if status.can_read_log and not status.sample_4625:
        parts.append(
            "No 4625 events yet — enter a wrong password once to test, then Re-check."
        )

    return PermissionItem(
        id="security_events",
        title="Security event log",
        description=" ".join(parts),
        granted=granted,
        required=True,
        action_label="Open Event Viewer",
        settings_target=_settings_targets().get("security_events", ""),
        extra_detail=format_security_status(status),
    )


def _check_journal_linux() -> bool:
    r = subprocess.run(
        ["journalctl", "-u", "systemd-logind", "-n", "1", "--no-pager"],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0:
        return False
    err = (r.stderr or "").lower()
    return "insufficient privileges" not in err


def _check_macos_logs() -> bool:
    r = subprocess.run(["log", "show", "--last", "1s"], capture_output=True, text=True, timeout=15)
    return r.returncode == 0


def gather_permissions() -> list[PermissionItem]:
    targets = _settings_targets()
    items = [
        PermissionItem(
            "camera", "Camera", "Webcam capture on security events.", _check_camera(), True,
            "Camera settings", targets.get("camera", ""),
        ),
        PermissionItem(
            "notifications", "Notifications", "Desktop alerts.", _check_notifications(), False,
            "Notification settings", targets.get("notifications", ""),
        ),
        PermissionItem(
            "keyring", "Credential storage", "Encryption password storage.", _check_keyring(), True,
            "Credential settings", targets.get("keyring", ""),
        ),
        PermissionItem(
            "storage", "Data folder", f"Write access to {CONFIG_DIR}.", _check_storage(), True,
            "Open folder", targets.get("storage", ""),
        ),
    ]
    system = platform.system()
    if system == "Windows":
        items.append(_windows_security_item())
    elif system == "Darwin":
        items.append(PermissionItem(
            "security_events", "System logs", "Login/lock events.", _check_macos_logs(), True,
            "Privacy", targets.get("security_events", ""),
        ))
    elif system == "Linux":
        items.append(PermissionItem(
            "security_events", "Journal", "systemd-logind events.", _check_journal_linux(), True,
            "Help", targets.get("security_events", ""),
        ))
    return items


def missing_required_permissions() -> list[PermissionItem]:
    return [p for p in gather_permissions() if p.required and not p.granted]


def fix_windows_security_events(parent: tk.Misc) -> None:
    from smd.windows_security import (
        diagnose_security_log,
        format_security_status,
        grant_event_log_readers_hint,
        launch_admin_fix_script,
    )

    status = diagnose_security_log()
    msg = (
        format_security_status(status)
        + "\n\n"
        "YES = Run FULL fix as Administrator\n"
        "  (audit policy + Event Log Readers + test)\n\n"
        "NO = Show manual instructions only"
    )

    if messagebox.askyesno("Fix Security log", msg, parent=parent):
        desktop_script = launch_admin_fix_script()
        messagebox.showinfo(
            "Administrator fix",
            "1. Approve the UAC prompt\n"
            "2. Wait until the blue window shows SUCCESS (or Done)\n"
            "3. Sign out and sign back in to Windows\n"
            "4. Open Secure Monitor → Permissions → Re-check\n\n"
            f"Script also saved to:\n{desktop_script}",
            parent=parent,
        )
    else:
        messagebox.showinfo("How to fix", grant_event_log_readers_hint(), parent=parent)


def request_permission_by_id(perm_id: str, parent: tk.Misc) -> bool:
    if perm_id == "camera":
        ok = _check_camera()
        if not ok:
            open_system_target(_settings_targets().get("camera", ""))
        return ok
    if perm_id == "notifications":
        send_alert("Secure Monitor", "Test notification", force=True)
        return _check_notifications()
    if perm_id == "keyring":
        return _check_keyring()
    if perm_id == "storage":
        return _check_storage()
    if perm_id == "security_events" and platform.system() == "Windows":
        fix_windows_security_events(parent)
        return _windows_security_item().granted
    if perm_id == "security_events":
        open_system_target(_settings_targets().get("security_events", ""))
        return gather_permissions()[-1].granted
    return False


class PermissionsWizard(tk.Toplevel):
    def __init__(self, parent, *, blocking=True):
        super().__init__(parent)
        self.title("Permissions")
        self.geometry("680x560")
        self.transient(parent)
        self.grab_set()
        ttk.Label(
            self,
            text="Grant permissions for reliable monitoring.",
            wraplength=620,
        ).pack(padx=12, pady=8)
        self.frame = ttk.Frame(self)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=12)
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=12, pady=8)
        ttk.Button(bar, text="Re-check", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(bar, text="Request all", command=self._all).pack(side=tk.LEFT, padx=6)
        if platform.system() == "Windows":
            ttk.Button(bar, text="Fix Security log…", command=lambda: fix_windows_security_events(self)).pack(
                side=tk.LEFT, padx=6
            )
        ttk.Button(bar, text="Done", command=self.destroy).pack(side=tk.RIGHT)
        self.refresh()
        if blocking:
            self.wait_window()

    def refresh(self):
        for w in self.frame.winfo_children():
            w.destroy()
        for p in gather_permissions():
            row = ttk.LabelFrame(self.frame, text=p.title, padding=6)
            row.pack(fill=tk.X, pady=4)
            st = "OK" if p.granted else "MISSING"
            ttk.Label(row, text=f"Status: {st}", font=("", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(row, text=p.description, wraplength=600).pack(anchor=tk.W)
            if p.extra_detail:
                detail = tk.Text(row, height=5, wrap=tk.WORD, font=("Consolas", 9))
                detail.insert("1.0", p.extra_detail)
                detail.configure(state=tk.DISABLED)
                detail.pack(fill=tk.X, pady=4)
            btns = ttk.Frame(row)
            btns.pack(anchor=tk.W)
            ttk.Button(btns, text="Request / Fix", command=lambda i=p.id: self._one(i)).pack(
                side=tk.LEFT, padx=2
            )
            if p.settings_target:
                ttk.Button(
                    btns, text=p.action_label, command=lambda t=p.settings_target: open_system_target(t)
                ).pack(side=tk.LEFT, padx=2)
            if p.id == "security_events" and platform.system() == "Windows":
                ttk.Button(
                    btns, text="Run full fix (Admin)", command=lambda: fix_windows_security_events(self)
                ).pack(side=tk.LEFT, padx=2)

    def _one(self, perm_id: str):
        request_permission_by_id(perm_id, self)
        self.refresh()

    def _all(self):
        for p in gather_permissions():
            if not p.granted:
                request_permission_by_id(p.id, self)
        self.refresh()


def ensure_permissions(parent, *, force=False) -> bool:
    from smd.config import load_config, save_config

    if platform.system() == "Windows":
        from smd.setup_windows import is_security_ready, is_windows_setup_complete, run_interactive_setup

        if not is_windows_setup_complete() and not is_security_ready():
            if not run_interactive_setup(parent):
                return False

    cfg = load_config()
    missing = missing_required_permissions()
    if not force and cfg.get("permissions_setup_complete") and not missing:
        return True
    if missing and not messagebox.askyesno("Permissions", "Open permissions setup?", parent=parent):
        return False
    PermissionsWizard(parent, blocking=True)
    cfg = load_config()
    cfg["permissions_setup_complete"] = True
    save_config(cfg)
    return len(missing_required_permissions()) == 0 or messagebox.askyesno(
        "Continue?", "Some permissions still missing. Continue anyway?", parent=parent
    )
