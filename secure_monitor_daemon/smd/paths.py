from pathlib import Path

CONFIG_DIR = Path.home() / ".secure_monitor"
CAPTURE_FOLDER = CONFIG_DIR / "captures"
SALT_FILE = CONFIG_DIR / "salt.bin"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "state.json"
MANIFEST_FILE = CONFIG_DIR / "manifest.jsonl"
PID_FILE = CONFIG_DIR / "worker.pid"
STOP_FILE = CONFIG_DIR / "worker.stop"
HEARTBEAT_FILE = CONFIG_DIR / "worker.heartbeat"
LOG_FILE = CONFIG_DIR / "worker.log"
GUI_PIN_FILE = CONFIG_DIR / "gui_pin.hash"

KEYRING_SERVICE = "secure_monitor_daemon"
KEYRING_USER = "encryption_password"

SEEN_MAX = 500
POLL_INTERVAL_IDLE = 15
POLL_INTERVAL_BURST = 3
POLL_BURST_DURATION = 45
CAPTURE_DEBOUNCE_SEC = 20
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_RETRIES = 3

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CAPTURE_FOLDER.mkdir(parents=True, exist_ok=True)
