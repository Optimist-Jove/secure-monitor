# Secure Monitor Daemon

Background security monitor: webcam capture on boot, failed login, and screen lock.

## End-user install (Windows)

1. `pip install -r requirements.txt`
2. Run the app once: `python secure_monitor_daemon\secure_monitor_daemon.py`
3. Complete **first-time setup** (one UAC prompt for Windows — required for all users)
4. Done — monitoring runs in the background

New users should **not** need manual Event Log Readers steps if they complete first-run setup.

## IT / lab deployment (all users on a PC)

Run **once as Administrator**:

```powershell
cd secure_monitor_daemon\scripts
.\Install-SecureMonitor.ps1
```

Then each user logs in and opens the app once (or runs `Fix-SecurityLog-Admin.ps1`).

## How we avoid the Security log issue

| Layer | What it does |
|-------|----------------|
| **First-run wizard** | Automatically launches elevated setup (audit + Event Log Readers) |
| **Default elevated worker** | Task Scheduler runs monitor with privileges to read Security log |
| **Bundled fix script** | `smd/resources/Fix-SecurityLog-Admin.ps1` copied to Desktop + `%USERPROFILE%\.secure_monitor\` |
| **Permission logic** | Shows OK after `windows_setup_complete` + elevated worker |

## Windows — if Security log still shows MISSING

1. Run first-time setup again: **Permissions → Run full fix (Admin)**
2. Sign out and back in
3. Ensure **Run worker elevated** is checked → **Enable startup** again

## CLI

| Command | Description |
|---------|-------------|
| `python secure_monitor_daemon.py` | GUI |
| `python secure_monitor_daemon.py --worker` | Background worker |
| `python secure_monitor_daemon.py --setup-permissions` | Permissions only |

## Data

`%USERPROFILE%\.secure_monitor\`

## Build EXE and installer (Windows)

**Requirements:** Python 3.10+, pip. Optional: [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the setup wizard.

```powershell
cd secure_monitor_daemon
.\build.ps1
```

Outputs:

| Output | Path |
|--------|------|
| Standalone app | `secure_monitor_daemon\dist\SecureMonitor.exe` |
| Installer (with disclaimer) | `installer\output\SecureMonitor-Setup.exe` |

The installer shows **DISCLAIMER.txt** on a license page. The user must choose **I accept** to continue or **I do not accept** to cancel.

Without Inno Setup, `build.ps1` still builds `SecureMonitor.exe` only.

## Legal

Use only on systems you own or are authorized to monitor.
