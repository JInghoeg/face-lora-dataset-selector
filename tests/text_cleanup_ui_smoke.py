"""Offscreen smoke for the extracted Text Cleanup Qt presentation."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
        Path.cwd(),
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
