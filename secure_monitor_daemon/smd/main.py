import argparse
import tkinter as tk

from smd.gui import gui_main
from smd.permissions import PermissionsWizard
from smd.worker import worker_main


def parse_args():
    p = argparse.ArgumentParser(description="Secure Monitor")
    p.add_argument("--worker", action="store_true")
    p.add_argument("--gui", action="store_true")
    p.add_argument("--setup-permissions", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    if args.worker:
        worker_main()
    elif args.setup_permissions:
        root = tk.Tk()
        root.withdraw()
        PermissionsWizard(root, blocking=True)
        root.destroy()
    else:
        gui_main()


if __name__ == "__main__":
    main()
