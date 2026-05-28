import shutil
from tkinter import messagebox

from smd.config import load_config, save_config
from smd.paths import CONFIG_DIR
from smd.process import stop_worker
from smd.startup import remove_from_startup


def full_uninstall(*, remove_captures: bool = False) -> None:
    stop_worker()
    remove_from_startup()
    cfg = load_config()
    cfg["monitor_enabled"] = False
    cfg["startup_enabled"] = False
    save_config(cfg)
    if remove_captures and CONFIG_DIR.exists():
        shutil.rmtree(CONFIG_DIR, ignore_errors=True)
