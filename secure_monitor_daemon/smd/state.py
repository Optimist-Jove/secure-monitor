import json
import time
from copy import deepcopy
from datetime import datetime

from smd.paths import HEARTBEAT_FILE, STATE_FILE


def _default_state() -> dict:
    return {
        "last_record_ids": {},
        "last_event_times": {},
        "last_capture_times": {},
        "boot_id": None,
        "failure_timestamps": [],
        "burst_until": 0,
        "worker_started_at": None,
    }


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return {**_default_state(), **json.loads(STATE_FILE.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            pass
    return _default_state()


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def touch_heartbeat() -> None:
    HEARTBEAT_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")


def read_heartbeat() -> str | None:
    if HEARTBEAT_FILE.exists():
        return HEARTBEAT_FILE.read_text(encoding="utf-8").strip()
    return None


def is_heartbeat_stale(max_age_sec: int = 60) -> bool:
    hb = read_heartbeat()
    if not hb:
        return True
    try:
        last = datetime.fromisoformat(hb)
        return (datetime.now() - last).total_seconds() > max_age_sec
    except ValueError:
        return True


def should_debounce(reason: str, debounce_sec: int) -> bool:
    state = load_state()
    last = state.get("last_capture_times", {}).get(reason, 0)
    return (time.time() - last) < debounce_sec


def mark_capture(reason: str) -> None:
    state = load_state()
    state.setdefault("last_capture_times", {})[reason] = time.time()
    save_state(state)


def record_failure_event() -> int:
    state = load_state()
    now = time.time()
    window = state.get("failure_timestamps", [])
    window = [t for t in window if now - t < 3600]
    window.append(now)
    state["failure_timestamps"] = window
    save_state(state)
    return len(window)


def set_burst_mode(duration_sec: int = 45) -> None:
    state = load_state()
    state["burst_until"] = time.time() + duration_sec
    save_state(state)


def is_burst_mode() -> bool:
    return time.time() < load_state().get("burst_until", 0)


def update_record_cursor(event_id: str, record_id: int) -> None:
    state = load_state()
    cursors = state.setdefault("last_record_ids", {})
    prev = cursors.get(event_id, 0)
    if record_id > prev:
        cursors[event_id] = record_id
        save_state(state)


def get_record_cursor(event_id: str) -> int:
    return load_state().get("last_record_ids", {}).get(event_id, 0)


def set_boot_id(boot_id: str) -> None:
    state = load_state()
    state["boot_id"] = boot_id
    save_state(state)


def get_boot_id() -> str | None:
    return load_state().get("boot_id")


def is_new_boot(current_boot_id: str) -> bool:
    prev = get_boot_id()
    if prev is None:
        set_boot_id(current_boot_id)
        return True
    if prev != current_boot_id:
        set_boot_id(current_boot_id)
        return True
    return False
