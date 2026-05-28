import tempfile
from pathlib import Path


def test_debounce(monkeypatch):
    from smd import state as st

    with tempfile.TemporaryDirectory() as tmp:
        sf = Path(tmp) / "state.json"
        monkeypatch.setattr(st, "STATE_FILE", sf)
        assert st.should_debounce("failed_login", 20) is False
        st.mark_capture("failed_login")
        assert st.should_debounce("failed_login", 20) is True
