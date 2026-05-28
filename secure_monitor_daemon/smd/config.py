import json
from copy import deepcopy

from smd.paths import CONFIG_FILE

SCHEMA_VERSION = 3

DEFAULT_CONFIG = {
    "schema_version": SCHEMA_VERSION,
    "auto_encrypt": True,
    "alerts_enabled": True,
    "capture_on_boot": True,
    "capture_on_login": True,
    "capture_on_lock": True,
    "capture_on_unlock": False,
    "capture_on_failed_login": True,
    "capture_on_success_login": False,
    "monitor_enabled": False,
    "startup_enabled": False,
    "permissions_setup_complete": False,
    "windows_setup_complete": False,
    "first_run_complete": False,
    "retention_days": 30,
    "max_captures": 500,
    "capture_debounce_sec": 20,
    "failure_alert_threshold": 5,
    "failure_alert_window_sec": 600,
    "silent_hours_start": None,
    "silent_hours_end": None,
    "gui_pin_enabled": False,
    "verbose_logging": False,
    "use_dpapi_key_wrap": True,
    "run_worker_elevated": True,
}


def _migrate(data: dict) -> dict:
    import platform

    merged = {**DEFAULT_CONFIG, **data}
    if merged.get("schema_version", 0) < 2:
        merged["schema_version"] = SCHEMA_VERSION
        merged.setdefault("capture_on_login", merged.get("capture_on_boot", True))
        merged.setdefault("retention_days", 30)
        merged.setdefault("max_captures", 500)
    if merged.get("schema_version", 0) < 3:
        merged["schema_version"] = SCHEMA_VERSION
        merged.setdefault("windows_setup_complete", False)
        if platform.system() == "Windows" and "run_worker_elevated" not in data:
            merged["run_worker_elevated"] = True
    return merged


def load_config() -> dict:
    import platform

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return _migrate(data)
        except (json.JSONDecodeError, OSError):
            pass
    cfg = deepcopy(DEFAULT_CONFIG)
    if platform.system() == "Windows":
        cfg["run_worker_elevated"] = True
    return cfg


def save_config(config: dict) -> None:
    config["schema_version"] = SCHEMA_VERSION
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
