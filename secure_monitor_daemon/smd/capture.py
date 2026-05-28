import time
from datetime import datetime
from pathlib import Path

import cv2

from smd.camera_util import open_camera, read_frame
from smd.alerts import send_capture_alert
from smd.config import load_config
from smd.crypto import encrypt_file, get_encryption_key
from smd.logging_setup import log_message
from smd.manifest import append_record
from smd.paths import (
    CAMERA_HEIGHT,
    CAMERA_RETRIES,
    CAMERA_WIDTH,
    CAPTURE_FOLDER,
    CAPTURE_DEBOUNCE_SEC,
)
from smd.retention import apply_retention
from smd.state import mark_capture, record_failure_event, should_debounce


def list_captures(reason_filter: str | None = None) -> list[Path]:
    files = [
        p
        for p in CAPTURE_FOLDER.iterdir()
        if p.is_file() and (".png" in p.name or p.name.endswith(".enc"))
    ]
    if reason_filter:
        files = [p for p in files if f"_{reason_filter}_" in p.name]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def capture_image(save_dir: Path, reason: str) -> Path | None:
    for attempt in range(1, CAMERA_RETRIES + 1):
        cap = open_camera(0)
        if not cap.isOpened():
            log_message(f"Camera not accessible (attempt {attempt}/{CAMERA_RETRIES})")
            cap.release()
            time.sleep(1)
            continue
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            ret, frame = read_frame(cap)
        finally:
            cap.release()
        if ret and frame is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)
            file_path = save_dir / f"capture_{safe}_{timestamp}.png"
            cv2.imwrite(str(file_path), frame)
            log_message(f"Image saved: {file_path}")
            return file_path
        time.sleep(1)
    return None


def process_capture(reason: str, metadata: dict | None = None) -> Path | None:
    cfg = load_config()
    debounce = int(cfg.get("capture_debounce_sec", CAPTURE_DEBOUNCE_SEC))
    if should_debounce(reason, debounce):
        log_message(f"Capture debounced for reason: {reason}")
        return None

    path = capture_image(CAPTURE_FOLDER, reason)
    if path is None:
        return None

    mark_capture(reason)
    final_path = path

    if cfg.get("auto_encrypt", True):
        key = get_encryption_key()
        if key:
            try:
                final_path = encrypt_file(path, key)
            except Exception as exc:
                log_message(f"Auto-encrypt failed: {exc}")
        else:
            log_message("Auto-encrypt skipped: no keyring password.")

    append_record(final_path, reason, metadata)
    send_capture_alert(reason, final_path.name, metadata)

    if reason == "failed_login":
        from smd.state import load_state
        from smd.alerts import send_alert

        record_failure_event()
        threshold = int(cfg.get("failure_alert_threshold", 5))
        window = int(cfg.get("failure_alert_window_sec", 600))
        recent = [
            t for t in load_state().get("failure_timestamps", []) if time.time() - t < window
        ]
        if len(recent) >= threshold:
            send_alert(
                "Secure Monitor — Alert",
                f"{len(recent)} failed logins in {window // 60} minutes.",
                force=True,
            )

    apply_retention()
    return final_path


def test_capture() -> Path | None:
    return process_capture("test", {"manual": True})
