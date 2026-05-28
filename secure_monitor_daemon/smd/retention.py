from datetime import datetime, timedelta
from pathlib import Path

from smd.config import load_config
from smd.logging_setup import log_message
from smd.paths import CAPTURE_FOLDER


def apply_retention() -> int:
    cfg = load_config()
    removed = 0
    max_count = int(cfg.get("max_captures", 500))
    days = int(cfg.get("retention_days", 30))
    cutoff = datetime.now() - timedelta(days=days)

    files = sorted(
        [
            p
            for p in CAPTURE_FOLDER.iterdir()
            if p.is_file() and (p.suffix in (".png", ".enc") or p.name.endswith(".png.enc"))
        ],
        key=lambda p: p.stat().st_mtime,
    )

    for path in files:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1

    files = sorted(
        [p for p in CAPTURE_FOLDER.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    while len(files) > max_count:
        oldest = files.pop(0)
        oldest.unlink(missing_ok=True)
        removed += 1

    if removed:
        log_message(f"Retention: removed {removed} old capture(s).")
    return removed
