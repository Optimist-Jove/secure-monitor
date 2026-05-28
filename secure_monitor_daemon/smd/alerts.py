from datetime import datetime

from smd.config import load_config
from smd.logging_setup import log_message

try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None


def _in_silent_hours() -> bool:
    cfg = load_config()
    start = cfg.get("silent_hours_start")
    end = cfg.get("silent_hours_end")
    if not start or not end:
        return False
    try:
        now = datetime.now().time()
        t0 = datetime.strptime(start, "%H:%M").time()
        t1 = datetime.strptime(end, "%H:%M").time()
        if t0 <= t1:
            return t0 <= now <= t1
        return now >= t0 or now <= t1
    except ValueError:
        return False


def send_alert(title: str, message: str, *, force: bool = False) -> None:
    cfg = load_config()
    if not force and not cfg.get("alerts_enabled", True):
        return
    if _in_silent_hours():
        log_message(f"Alert suppressed (silent hours): {title}")
        return
    if plyer_notification is None:
        log_message(f"Alert: {title} — {message}")
        return
    try:
        plyer_notification.notify(
            title=title,
            message=message,
            app_name="Secure Monitor",
            timeout=12,
        )
    except Exception as exc:
        log_message(f"Alert failed: {exc}")


def send_capture_alert(reason: str, filename: str, metadata: dict | None = None) -> None:
    label = reason.replace("_", " ").title()
    extra = ""
    if metadata:
        user = metadata.get("username") or metadata.get("TargetUserName")
        if user:
            extra = f" User: {user}."
    send_alert("Secure Monitor", f"{label}: {filename}.{extra}")
