"""Cross-platform webcam open with Windows-friendly backends."""
from __future__ import annotations

import os
import platform
import time

import cv2

# Reduce OpenCV MSMF noise in console
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except AttributeError:
    pass


def open_camera(device_index: int = 0):
    """Try backends in order; MSMF often fails with async ReadSample on Windows."""
    backends: list[int | None] = [None]
    if platform.system() == "Windows":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]

    for api in backends:
        cap = cv2.VideoCapture(device_index, api) if api is not None else cv2.VideoCapture(device_index)
        if cap.isOpened():
            return cap
        cap.release()
        time.sleep(0.2)
    return cv2.VideoCapture(device_index)


def read_frame(cap, warmup_frames: int = 2):
    """Discard warmup frames then read one usable frame."""
    for _ in range(warmup_frames):
        cap.read()
        time.sleep(0.05)
    return cap.read()
