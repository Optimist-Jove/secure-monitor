import io
import platform
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
import tkinter as tk

import keyring
from cryptography.fernet import InvalidToken
from PIL import Image, ImageTk

from smd.capture import list_captures, test_capture
from smd.config import load_config, save_config
from smd.crypto import (
    decrypt_bytes,
    decrypt_folder,
    encrypt_folder,
    get_encryption_key,
    hash_gui_pin,
    store_encryption_password,
    verify_gui_pin,
)
from smd.diagnostics import run_diagnostics
from smd.manifest import load_records, stats_summary
from smd.paths import CAPTURE_FOLDER, CONFIG_DIR, GUI_PIN_FILE, KEYRING_SERVICE, KEYRING_USER
from smd.permissions import PermissionsWizard, ensure_permissions
from smd.process import is_worker_running, spawn_worker, stop_worker
from smd.startup import add_to_startup, remove_from_startup
from smd.state import is_heartbeat_stale, read_heartbeat
from smd.uninstall import full_uninstall


class CaptureViewer(ttk.Frame):
    def __init__(self, master, get_password):
        super().__init__(master)
        self.get_password = get_password
        self._photo = None
        self._paths: list[Path] = []
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="all")
        for val, label in [
            ("all", "All"), ("failed_login", "Failed login"), ("boot", "Boot"),
            ("lock", "Lock"), ("login", "Login"), ("test", "Test"),
        ]:
            ttk.Radiobutton(top, text=label, value=val, variable=self.filter_var, command=self.refresh).pack(side=tk.LEFT, padx=4)
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, pady=6)
        self.listbox = tk.Listbox(body, width=40, height=14)
        self.listbox.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview = ttk.Label(right, text="Select a capture", anchor=tk.CENTER)
        self.preview.pack(fill=tk.BOTH, expand=True)
        self.meta = ttk.Label(right, text="", wraplength=400)
        self.meta.pack(fill=tk.X, pady=4)
        btns = ttk.Frame(right)
        btns.pack(fill=tk.X)
        for txt, cmd in [
            ("Refresh", self.refresh), ("Delete", self.delete_selected),
            ("Export", self.export_selected), ("Open folder", self.open_folder),
        ]:
            ttk.Button(btns, text=txt, command=cmd).pack(side=tk.LEFT, padx=3)
        self.refresh()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        filt = self.filter_var.get()
        self._paths = list_captures(None if filt == "all" else filt)
        for p in self._paths:
            self.listbox.insert(tk.END, p.name)

    def _load_image(self, path: Path) -> Image.Image:
        if path.name.endswith(".enc"):
            pwd = self.get_password()
            if not pwd:
                raise ValueError("Password required")
            key = get_encryption_key(pwd)
            return Image.open(io.BytesIO(decrypt_bytes(path, key)))
        return Image.open(path)

    def on_select(self, _e=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self._paths[sel[0]]
        try:
            img = self._load_image(path)
            img.thumbnail((500, 380))
            self._photo = ImageTk.PhotoImage(img)
            self.preview.configure(image=self._photo, text="")
        except Exception as exc:
            self.preview.configure(image="", text=str(exc))
        rec = next((r for r in load_records() if r.get("file") == path.name), None)
        self.meta.configure(text=json_meta(rec) if rec else path.name)

    def delete_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self._paths[sel[0]]
        if messagebox.askyesno("Delete", f"Delete {path.name}?"):
            path.unlink(missing_ok=True)
            self.refresh()

    def export_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        dest = filedialog.asksaveasfilename(defaultextension=".png")
        if not dest:
            return
        path = self._paths[sel[0]]
        if path.name.endswith(".enc"):
            data = decrypt_bytes(path, get_encryption_key(self.get_password()))
            Path(dest).write_bytes(data)
        else:
            import shutil
            shutil.copy(path, dest)

    def open_folder(self):
        folder = str(CAPTURE_FOLDER)
        if platform.system() == "Windows":
            import os
            os.startfile(folder)  # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)


def json_meta(rec: dict | None) -> str:
    if not rec:
        return ""
    parts = [rec.get("reason", ""), rec.get("timestamp", "")]
    meta = rec.get("metadata") or {}
    if meta.get("message"):
        parts.append(meta["message"][:200])
    return " | ".join(parts)


def first_run_wizard(root):
    cfg = load_config()
    if cfg.get("first_run_complete"):
        return
    if not messagebox.askyesno(
        "Welcome to Secure Monitor",
        "First-time setup will:\n"
        "  1. Configure Windows security logging (one UAC prompt)\n"
        "  2. Set camera and other permissions\n"
        "  3. Set encryption password and start monitoring\n\n"
        "Continue?",
        parent=root,
    ):
        return

    if platform.system() == "Windows":
        from smd.setup_windows import run_interactive_setup, finalize_startup_after_setup

        run_interactive_setup(root)

    PermissionsWizard(root, blocking=True)
    pwd = simpledialog.askstring("Password", "Set encryption password:", show="*", parent=root)
    if pwd:
        store_encryption_password(pwd)

    if platform.system() == "Windows":
        from smd.setup_windows import finalize_startup_after_setup

        finalize_startup_after_setup()
    elif messagebox.askyesno("Startup", "Enable startup at login?", parent=root):
        add_to_startup()
        spawn_worker()
    else:
        spawn_worker()

    cfg = load_config()
    cfg["first_run_complete"] = True
    cfg["permissions_setup_complete"] = True
    save_config(cfg)
    messagebox.showinfo(
        "Setup complete",
        "Secure Monitor is configured.\n"
        "Monitoring runs in the background after you close this window.",
        parent=root,
    )


def pin_gate(root) -> bool:
    cfg = load_config()
    if not cfg.get("gui_pin_enabled") or not GUI_PIN_FILE.exists():
        return True
    for _ in range(3):
        pin = simpledialog.askstring("PIN", "Enter app PIN:", show="*", parent=root)
        if pin and verify_gui_pin(pin, GUI_PIN_FILE.read_text(encoding="utf-8")):
            return True
    messagebox.showerror("PIN", "Access denied.")
    return False


def gui_main() -> None:
    if platform.system() == "Windows":
        from smd.setup_windows import apply_windows_defaults

        apply_windows_defaults()

    root = tk.Tk()
    root.title("Secure Monitor")
    root.geometry("960x680")
    root.minsize(860, 600)
    if not pin_gate(root):
        root.destroy()
        return

    cfg = load_config()

    def get_password():
        p = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        return p or simpledialog.askstring("Password", "Encryption password:", show="*", parent=root)

    status = ttk.Label(root, text="")
    status.pack(anchor=tk.W, padx=10, pady=6)

    def refresh_status():
        if is_worker_running():
            hb = read_heartbeat() or "no heartbeat"
            stale = is_heartbeat_stale(90)
            status.configure(
                text=f"Worker: RUNNING | Heartbeat: {hb}" + (" (STALE)" if stale else "")
            )
        else:
            status.configure(text="Worker: STOPPED")

    nb = ttk.Notebook(root)
    nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
    controls = ttk.Frame(nb, padding=8)
    captures_tab = ttk.Frame(nb, padding=8)
    dashboard = ttk.Frame(nb, padding=8)
    diag_tab = ttk.Frame(nb, padding=8)
    for tab, name in [(controls, "Controls"), (captures_tab, "Captures"), (dashboard, "Dashboard"), (diag_tab, "Diagnostics")]:
        nb.add(tab, text=name)

    def persist():
        c = load_config()
        for k, v in [
            ("auto_encrypt", ae.get()), ("alerts_enabled", al.get()),
            ("capture_on_boot", cb.get()), ("capture_on_login", cln.get()),
            ("capture_on_lock", clk.get()), ("capture_on_failed_login", cfl.get()),
            ("capture_on_success_login", csl.get()), ("capture_on_unlock", cu.get()),
            ("retention_days", int(ret_days.get() or 30)),
            ("max_captures", int(max_cap.get() or 500)),
            ("failure_alert_threshold", int(thresh.get() or 5)),
        ]:
            c[k] = v
        save_config(c)

    def start():
        if not ensure_permissions(root):
            return
        persist()
        if not keyring.get_password(KEYRING_SERVICE, KEYRING_USER):
            p = simpledialog.askstring("Password", "Set encryption password:", show="*", parent=root)
            if p:
                store_encryption_password(p)
        spawn_worker()
        refresh_status()
        messagebox.showinfo("Started", "Monitoring runs in background after you close this window.", parent=root)

    def stop():
        if stop_worker():
            refresh_status()
            messagebox.showinfo("Stopped", "Monitoring stopped.", parent=root)

    mon = ttk.LabelFrame(controls, text="Monitoring", padding=8)
    mon.pack(fill=tk.X)
    ttk.Button(mon, text="Start Monitoring", command=start).pack(fill=tk.X, pady=2)
    ttk.Button(mon, text="Stop Monitoring", command=stop).pack(fill=tk.X, pady=2)
    ttk.Button(mon, text="Test capture now", command=lambda: (test_capture(), viewer.refresh())).pack(fill=tk.X, pady=2)

    sett = ttk.LabelFrame(controls, text="Settings", padding=8)
    sett.pack(fill=tk.X, pady=8)
    ae, al = tk.BooleanVar(value=cfg.get("auto_encrypt", True)), tk.BooleanVar(value=cfg.get("alerts_enabled", True))
    cb = tk.BooleanVar(value=cfg.get("capture_on_boot", True))
    cln = tk.BooleanVar(value=cfg.get("capture_on_login", True))
    clk = tk.BooleanVar(value=cfg.get("capture_on_lock", True))
    cfl = tk.BooleanVar(value=cfg.get("capture_on_failed_login", True))
    csl = tk.BooleanVar(value=cfg.get("capture_on_success_login", False))
    cu = tk.BooleanVar(value=cfg.get("capture_on_unlock", False))
    for text, var in [
        ("Auto-encrypt", ae), ("Alerts", al), ("Capture on boot", cb), ("Capture on login", cln),
        ("Capture on lock", clk), ("Capture on failed login", cfl),
        ("Capture on successful login (4624)", csl), ("Capture on unlock", cu),
    ]:
        ttk.Checkbutton(sett, text=text, variable=var, command=persist).pack(anchor=tk.W)
    adv = ttk.Frame(sett)
    adv.pack(fill=tk.X, pady=4)
    ttk.Label(adv, text="Retention days").grid(row=0, column=0, sticky=tk.W)
    ret_days = ttk.Entry(adv, width=6)
    ret_days.insert(0, str(cfg.get("retention_days", 30)))
    ret_days.grid(row=0, column=1)
    ttk.Label(adv, text="Max captures").grid(row=0, column=2, padx=8)
    max_cap = ttk.Entry(adv, width=6)
    max_cap.insert(0, str(cfg.get("max_captures", 500)))
    max_cap.grid(row=0, column=3)
    ttk.Label(adv, text="Fail alert threshold").grid(row=1, column=0, sticky=tk.W, pady=4)
    thresh = ttk.Entry(adv, width=6)
    thresh.insert(0, str(cfg.get("failure_alert_threshold", 5)))
    thresh.grid(row=1, column=1)

    tools = ttk.LabelFrame(controls, text="Tools", padding=8)
    tools.pack(fill=tk.X)
    ttk.Button(tools, text="Permissions setup", command=lambda: PermissionsWizard(root)).pack(fill=tk.X, pady=2)
    if platform.system() == "Windows":
        from smd.permissions import fix_windows_security_events
        ttk.Button(tools, text="Fix Security log (4625/4800)", command=lambda: fix_windows_security_events(root)).pack(
            fill=tk.X, pady=2
        )
        rev = tk.BooleanVar(value=cfg.get("run_worker_elevated", False))
        def toggle_elevated():
            c = load_config()
            c["run_worker_elevated"] = rev.get()
            save_config(c)
            if c["startup_enabled"]:
                add_to_startup()
        ttk.Checkbutton(
            tools, text="Run worker elevated (reads Security log)", variable=rev, command=toggle_elevated
        ).pack(anchor=tk.W, pady=2)
    ttk.Button(tools, text="Enable startup", command=lambda: (ensure_permissions(root), add_to_startup(), spawn_worker(), refresh_status())).pack(fill=tk.X, pady=2)
    ttk.Button(tools, text="Disable startup", command=remove_from_startup).pack(fill=tk.X, pady=2)
    ttk.Button(tools, text="Set GUI PIN", command=lambda: set_pin(root)).pack(fill=tk.X, pady=2)

    def set_pin(parent):
        pin = simpledialog.askstring("PIN", "New PIN:", show="*", parent=parent)
        if pin:
            GUI_PIN_FILE.write_text(hash_gui_pin(pin), encoding="utf-8")
            c = load_config()
            c["gui_pin_enabled"] = True
            save_config(c)

    def encrypt_all():
        p = simpledialog.askstring("Password", "Password:", show="*", parent=root)
        if p:
            store_encryption_password(p)
            encrypt_folder(CAPTURE_FOLDER, get_encryption_key(p))
            viewer.refresh()

    def decrypt_all():
        p = get_password()
        if p:
            try:
                decrypt_folder(CAPTURE_FOLDER, get_encryption_key(p))
                viewer.refresh()
            except InvalidToken:
                messagebox.showerror("Error", "Wrong password", parent=root)

    ttk.Button(tools, text="Encrypt all", command=encrypt_all).pack(fill=tk.X, pady=2)
    ttk.Button(tools, text="Decrypt all", command=decrypt_all).pack(fill=tk.X, pady=2)
    ttk.Button(tools, text="Full uninstall", command=lambda: uninstall_confirm(root)).pack(fill=tk.X, pady=2)

    viewer = CaptureViewer(captures_tab, get_password)
    viewer.pack(fill=tk.BOTH, expand=True)

    dash_text = tk.Text(dashboard, height=20, wrap=tk.WORD)
    dash_text.pack(fill=tk.BOTH, expand=True)
    ttk.Button(dashboard, text="Refresh stats", command=lambda: show_stats(dash_text)).pack(pady=4)
    show_stats(dash_text)

    diag_list = tk.Listbox(diag_tab, height=22)
    diag_list.pack(fill=tk.BOTH, expand=True, pady=4)
    ttk.Button(diag_tab, text="Run diagnostics", command=lambda: fill_diag(diag_list)).pack()
    fill_diag(diag_list)

    def tick():
        refresh_status()
        root.after(5000, tick)

    refresh_status()
    root.after(5000, tick)
    first_run_wizard(root)
    if not load_config().get("permissions_setup_complete"):
        root.after(400, lambda: PermissionsWizard(root, blocking=False))

    def on_close():
        persist()
        if is_worker_running():
            messagebox.showinfo("Running", "Monitoring continues in background.", parent=root)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


def show_stats(widget):
    widget.delete("1.0", tk.END)
    s = stats_summary()
    widget.insert(tk.END, f"Total captures (manifest): {s['total']}\n\nBy reason:\n")
    for k, v in s.get("by_reason", {}).items():
        widget.insert(tk.END, f"  {k}: {v}\n")
    widget.insert(tk.END, f"\nData folder: {CONFIG_DIR}\n")


def fill_diag(lst):
    lst.delete(0, tk.END)
    for name, detail, ok in run_diagnostics():
        lst.insert(tk.END, f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")


def uninstall_confirm(root):
    if messagebox.askyesno("Uninstall", "Stop monitoring and remove startup?", parent=root):
        rm = messagebox.askyesno("Data", "Also delete all captures and config?", parent=root)
        full_uninstall(remove_captures=rm)
        messagebox.showinfo("Done", "Uninstalled.", parent=root)
        root.destroy()
