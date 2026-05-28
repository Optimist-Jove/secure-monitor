import json
import platform
import subprocess
from datetime import datetime, timedelta

from smd.capture import process_capture
from smd.config import load_config
from smd.logging_setup import log_message
from smd.state import (
    get_record_cursor,
    is_burst_mode,
    set_burst_mode,
    update_record_cursor,
)


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log_message(f"Command failed: {exc}")
        return None
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        if err:
            log_message(f"Command error: {err[:300]}")
        return None
    return r


def get_system_boot_id() -> str:
    system = platform.system()
    if system == "Windows":
        script = "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')"
        r = _run(["powershell", "-Command", script])
        return (r.stdout.strip() if r else "") or "unknown"
    if system == "Linux":
        r = _run(["cat", "/proc/sys/kernel/random/boot_id"])
        return (r.stdout.strip() if r else "") or "unknown"
    if system == "Darwin":
        r = _run(["sysctl", "-n", "kern.bootsessionuuid"])
        return (r.stdout.strip() if r else "") or "unknown"
    return "unknown"


def poll_windows(config: dict) -> None:
    since = (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%S")
    event_map: list[tuple[str, int, str]] = []
    if config.get("capture_on_failed_login", True):
        event_map.append(("failed_login", 4625, "Failure"))
    if config.get("capture_on_lock", True):
        event_map.append(("lock", 4800, "Lock"))
    if config.get("capture_on_unlock", False):
        event_map.append(("unlock", 4801, "Unlock"))
    if config.get("capture_on_success_login", False):
        event_map.append(("success_login", 4624, "Success"))

    ids = ",".join(str(e[1]) for e in event_map)
    if not ids:
        return

    script = f"""
$since = [datetime]'{since}'
$events = Get-WinEvent -FilterHashtable @{{
  LogName='Security'; Id=@({ids}); StartTime=$since
}} -ErrorAction SilentlyContinue |
  Select-Object Id, RecordId, TimeCreated, Message |
  ConvertTo-Json -Compress
if (-not $events) {{ '[]' }} else {{ $events }}
"""
    result = _run(["powershell", "-Command", script], timeout=45)
    if not result or not result.stdout.strip():
        return
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return
    if isinstance(payload, dict):
        payload = [payload]

    id_to_reason = {e[1]: (e[0], e[2]) for e in event_map}
    for ev in payload:
        eid = int(ev.get("Id", 0))
        if eid not in id_to_reason:
            continue
        reason, _label = id_to_reason[eid]
        record_id = int(ev.get("RecordId", 0))
        cursor = get_record_cursor(str(eid))
        if record_id <= cursor:
            continue
        update_record_cursor(str(eid), record_id)
        msg = ev.get("Message", "")
        meta = {"message": msg[:500], "time": ev.get("TimeCreated")}
        if reason in ("lock", "unlock"):
            set_burst_mode()
        process_capture(reason, meta)


def poll_macos(config: dict) -> None:
    if config.get("capture_on_failed_login", True):
        r = _run(
            [
                "log", "show", "--style", "json", "--last", "2m",
                "--predicate", 'eventMessage CONTAINS "authentication failure"',
            ]
        )
        if r and r.stdout.strip():
            key = hash(r.stdout.strip()[-400:])
            from smd.state import load_state, save_state

            state = load_state()
            seen = state.setdefault("mac_seen", {})
            if seen.get("failed_login") != key:
                seen["failed_login"] = key
                save_state(state)
                process_capture("failed_login")

    if config.get("capture_on_lock", True):
        r = _run(
            [
                "log", "show", "--style", "json", "--last", "2m",
                "--predicate", 'eventMessage CONTAINS "lock" OR eventMessage CONTAINS "Locked"',
            ]
        )
        if r and r.stdout.strip():
            from smd.state import load_state, save_state

            key = hash(r.stdout.strip()[-400:])
            state = load_state()
            seen = state.setdefault("mac_seen", {})
            if seen.get("lock") != key:
                seen["lock"] = key
                save_state(state)
                set_burst_mode()
                process_capture("lock")


def poll_linux(config: dict) -> None:
    r = _run(["journalctl", "-u", "systemd-logind", "-n", "30", "--no-pager", "-o", "json"])
    if not r:
        return
    from smd.state import load_state, save_state

    state = load_state()
    seen_list = state.setdefault("linux_seen", [])
    seen = set(seen_list) if isinstance(seen_list, list) else set()
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = (entry.get("MESSAGE") or "").lower()
        key = entry.get("__CURSOR") or entry.get("SYSLOG_IDENTIFIER", "") + msg[:80]
        if key in seen:
            continue
        reason = None
        if config.get("capture_on_failed_login", True) and "authentication failure" in msg:
            reason = "failed_login"
        elif config.get("capture_on_lock", True) and "session locked" in msg:
            reason = "lock"
            set_burst_mode()
        elif config.get("capture_on_unlock", False) and "session unlocked" in msg:
            reason = "unlock"
        if reason:
            seen.add(key)
            state["linux_seen"] = list(seen)[-500:]
            save_state(state)
            process_capture(reason, {"journal": msg[:300]})


def run_poll_cycle() -> None:
    config = load_config()
    system = platform.system()
    if system == "Windows":
        poll_windows(config)
    elif system == "Darwin":
        poll_macos(config)
    elif system == "Linux":
        poll_linux(config)
    else:
        raise OSError(f"Unsupported OS: {system}")


def get_poll_interval() -> int:
    from smd.paths import POLL_INTERVAL_BURST, POLL_INTERVAL_IDLE

    return POLL_INTERVAL_BURST if is_burst_mode() else POLL_INTERVAL_IDLE
