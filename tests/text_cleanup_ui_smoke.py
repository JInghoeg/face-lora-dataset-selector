"""Offscreen smoke for the extracted Text Cleanup Qt presentation."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from application import SelectorApplication
from ui.qt import SubtitleTab


def main():
    backend = SelectorApplication()
    app = QApplication.instance() or QApplication([])
    if not backend.feature_available("text_cleanup"):
        print("Text Cleanup optional feature unavailable; UI smoke skipped")
        return 0

    tab = SubtitleTab(
        backend,
        ROOT,
        backend.cache_root / "thumbnails",
    )
    assert tab.backend is backend
    assert tab.preview is not None
    assert tab.scan is not None
    tab.close()
    app.processEvents()
    print("Text Cleanup UI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
