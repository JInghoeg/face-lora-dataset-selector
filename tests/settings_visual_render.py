"""Real-Qt visual render for the actual v0.4 SettingsPage widget."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "src" / "ui" / "qt" / "settings_page.py"
SPEC = importlib.util.spec_from_file_location("settings_page_visual", FILE)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def pump(app, count=8):
    for _ in range(count):
        app.processEvents()


def render(out_dir: Path):
    app = QApplication.instance() or QApplication([])

    font_path = os.environ.get("SETTINGS_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    page = module.SettingsPage(
        auto_check=True,
        version="v0.4.0",
        inference_device="gpu",
        background_enrichment=True,
        theme="dark",
    )
    page.resize(1040, 720)
    page.show()
    pump(app)

    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    page.navigation.setCurrentRow(0)
    pump(app)
    p = out_dir / "settings_general.png"
    assert page.grab().save(str(p)), p
    outputs.append(p)

    page.navigation.setCurrentRow(1)
    pump(app)
    p = out_dir / "settings_performance.png"
    assert page.grab().save(str(p)), p
    outputs.append(p)

    page.updates.set_status("available", latest="v0.4.1", download_bytes=35_000_000)
    page.navigation.setCurrentRow(2)
    pump(app)
    p = out_dir / "settings_updates_available.png"
    assert page.grab().save(str(p)), p
    outputs.append(p)

    page.close()
    pump(app)
    for item in outputs:
        print(item)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    render(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
