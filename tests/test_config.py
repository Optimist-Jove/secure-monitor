import json
import tempfile
from pathlib import Path

import pytest


def test_config_migrate(monkeypatch):
    from smd import config as cfg_mod

    with tempfile.TemporaryDirectory() as tmp:
        cf = Path(tmp) / "config.json"
        cf.write_text(json.dumps({"schema_version": 0, "auto_encrypt": False}), encoding="utf-8")
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", cf)
        data = cfg_mod.load_config()
        assert data["schema_version"] == cfg_mod.SCHEMA_VERSION
        assert "retention_days" in data
