import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path

from smd.crypto import manifest_hmac_key
from smd.paths import MANIFEST_FILE


def append_record(path: Path, reason: str, metadata: dict | None = None) -> None:
    data = path.read_bytes() if path.exists() else b""
    record = {
        "timestamp": datetime.now().isoformat(),
        "file": path.name,
        "reason": reason,
        "sha256": hashlib.sha256(data).hexdigest(),
        "metadata": metadata or {},
    }
    line = json.dumps(record, ensure_ascii=False)
    mk = manifest_hmac_key()
    if mk:
        sig = hmac.new(mk, line.encode(), hashlib.sha256).hexdigest()
        line = json.dumps({"record": record, "sig": sig}, ensure_ascii=False)
    with MANIFEST_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_records() -> list[dict]:
    if not MANIFEST_FILE.exists():
        return []
    records = []
    for line in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if "record" in obj and "sig" in obj:
                mk = manifest_hmac_key()
                payload = json.dumps({"record": obj["record"]}, ensure_ascii=False)
                if mk and not hmac.compare_digest(
                    obj["sig"],
                    hmac.new(mk, payload.encode(), hashlib.sha256).hexdigest(),
                ):
                    obj["record"]["tampered"] = True
                records.append(obj["record"])
            else:
                records.append(obj)
        except json.JSONDecodeError:
            continue
    return records


def stats_summary() -> dict:
    records = load_records()
    by_reason: dict[str, int] = {}
    for r in records:
        reason = r.get("reason", "unknown")
        by_reason[reason] = by_reason.get(reason, 0) + 1
    return {"total": len(records), "by_reason": by_reason}
