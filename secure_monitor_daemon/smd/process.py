import os
import platform
import subprocess
import sys
import time

from smd.logging_setup import log_message
from smd.paths import PID_FILE, STOP_FILE


def get_app_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "secure_monitor_daemon.py"))


def get_smd_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def get_worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker"]
    return [sys.executable, get_app_path(), "--worker"]


def get_gui_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--gui"]
    return [sys.executable, get_app_path(), "--gui"]


def read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def write_pid(pid: int) -> None:
    PID_FILE.write_text(str(pid), encoding="utf-8")


def remove_pid_file() -> None:
    PID_FILE.unlink(missing_ok=True)


def clear_stop_file() -> None:
    STOP_FILE.unlink(missing_ok=True)


def request_worker_stop() -> None:
    STOP_FILE.touch()


def should_worker_stop() -> bool:
    return STOP_FILE.exists()


def is_process_alive(pid: int) -> bool:
    if platform.system() == "Windows":
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_worker_running() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    if is_process_alive(pid):
        return True
    remove_pid_file()
    return False


def spawn_worker() -> None:
    if is_worker_running():
        return
    cmd = get_worker_command()
    kwargs: dict = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        **kwargs,
    )
    time.sleep(0.6)


def stop_worker(timeout: float = 25.0) -> bool:
    if not is_worker_running():
        clear_stop_file()
        return True
    request_worker_stop()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_worker_running():
            clear_stop_file()
            return True
        time.sleep(0.5)
    log_message("Worker did not stop in time.", level=40)
    return not is_worker_running()
