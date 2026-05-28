# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
RESOURCE_PS1 = SPEC_DIR / "smd" / "resources" / "Fix-SecurityLog-Admin.ps1"

datas = []
if RESOURCE_PS1.exists():
    datas.append((str(RESOURCE_PS1), os.path.join("smd", "resources")))

a = Analysis(
    ["secure_monitor_daemon.py"],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "smd",
        "smd.main",
        "smd.worker",
        "smd.gui",
        "smd.events",
        "smd.capture",
        "smd.camera_util",
        "smd.win_elevate",
        "smd.crypto",
        "smd.config",
        "smd.permissions",
        "smd.process",
        "smd.startup",
        "smd.setup_windows",
        "smd.windows_security",
        "smd.diagnostics",
        "smd.manifest",
        "smd.retention",
        "smd.alerts",
        "smd.state",
        "smd.logging_setup",
        "smd.paths",
        "smd.uninstall",
        "keyring",
        "keyring.backends",
        "keyring.backends.Windows",
        "plyer",
        "plyer.platforms.win.notification",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "cv2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

_icon = [str(SPEC_DIR / "smdicon.png")] if (SPEC_DIR / "smdicon.png").exists() else []

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SecureMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
