import os
import time

from smd.capture import process_capture
from smd.config import load_config, save_config
from smd.events import get_poll_interval, get_system_boot_id, run_poll_cycle
from smd.logging_setup import log_message, setup_logging
from smd.permissions import missing_required_permissions
from smd.process import (
    clear_stop_file,
    is_worker_running,
    read_pid,
    remove_pid_file,
    should_worker_stop,
    write_pid,
)
from smd.state import is_new_boot, touch_heartbeat


def worker_main() -> None:
    import platform

    if platform.system() == "Windows":
        from smd.setup_windows import apply_windows_defaults

        apply_windows_defaults()

    cfg = load_config()
    setup_logging(cfg.get("verbose_logging", False))

    if is_worker_running() and read_pid() != os.getpid():
        log_message("Worker already running; exiting.")
        return

    write_pid(os.getpid())
    clear_stop_file()
    cfg["monitor_enabled"] = True
    save_config(cfg)
    log_message("Worker started.")

    for perm in missing_required_permissions():
        log_message(f"Permission missing: {perm.title}")

    boot_id = get_system_boot_id()
    if is_new_boot(boot_id):
        if cfg.get("capture_on_boot", True):
            process_capture("boot", {"boot_id": boot_id})
        elif cfg.get("capture_on_login", True):
            process_capture("login", {"boot_id": boot_id})

    try:
        while not should_worker_stop():
            touch_heartbeat()
            try:
                run_poll_cycle()
            except Exception as exc:
                log_message(f"Poll error: {exc}", level=40)
            interval = get_poll_interval()
            for _ in range(interval):
                if should_worker_stop():
                    break
                time.sleep(1)
    finally:
        cfg = load_config()
        cfg["monitor_enabled"] = False
        save_config(cfg)
        remove_pid_file()
        clear_stop_file()
        log_message("Worker stopped.")
