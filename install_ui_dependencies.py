"""Install the selected Fluent UI dependencies without PySide6-Addons.

QFluentWidgets declares the PySide6 meta-package, which would install Addons.
The Auto Crop surface only uses QtWidgets/QtGui/QtCore APIs already provided by
PySide6-Essentials, proven by the repository UI spike.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys


BASE = [
    "darkdetect==0.8.0",
    "pywin32==312",
]

NODEPS = [
    "PySideSix-Frameless-Window==0.8.2",
    "PySide6-Fluent-Widgets==1.11.3",
]


def run(args):
    subprocess.check_call([sys.executable, "-m", "pip", *args])


def main():
    if sys.platform != "win32":
        raise SystemExit("Fluent UI runtime is currently supported on Windows only.")

    run(["install", "--no-cache-dir", *BASE])
    run(["install", "--no-cache-dir", "--no-deps", *NODEPS])

    import qfluentwidgets  # noqa: F401

    addons = importlib.util.find_spec("PySide6.QtCharts") is not None
    if addons:
        print(
            "WARNING: PySide6-Addons is already present in this environment; "
            "this installer did not install it."
        )
    else:
        print("Fluent UI runtime installed with PySide6-Essentials only.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
