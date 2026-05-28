from smd.capture import list_captures
from smd.config import load_config
from smd.events import get_system_boot_id
from smd.manifest import stats_summary
from smd.permissions import gather_permissions, missing_required_permissions
from smd.process import is_worker_running
from smd.startup import _launch_string
from smd.state import is_heartbeat_stale, read_heartbeat


def run_diagnostics() -> list[tuple[str, str, bool]]:
    results: list[tuple[str, str, bool]] = []
    results.append(("Worker process", "Running" if is_worker_running() else "Stopped", is_worker_running()))
    results.append(("Heartbeat", read_heartbeat() or "none", not is_heartbeat_stale(90)))
    results.append(("Boot ID", get_system_boot_id(), True))
    cfg = load_config()
    results.append(("Startup enabled", str(cfg.get("startup_enabled")), bool(cfg.get("startup_enabled"))))
    results.append(("Launch command", _launch_string()[:120], True))
    missing = missing_required_permissions()
    results.append(
        ("Permissions", f"{len(missing)} missing" if missing else "OK", len(missing) == 0)
    )
    caps = list_captures()
    results.append(("Captures on disk", str(len(caps)), len(caps) >= 0))
    stats = stats_summary()
    results.append(("Manifest entries", str(stats["total"]), True))
    for perm in gather_permissions():
        results.append((f"  {perm.title}", "OK" if perm.granted else "Missing", perm.granted))
    return results
