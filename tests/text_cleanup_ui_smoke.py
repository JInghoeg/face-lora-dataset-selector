"""Offscreen smoke for the extracted Text Cleanup Qt presentation."""
from __future__ import annotations

import os
import sys
from pathlib import Path
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QFileDialog

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

    # Selecting an input folder must immediately schedule a scan; users should
    # not have to discover and click a second button after folder selection.
    original_picker = QFileDialog.getExistingDirectory
    calls = []
    try:
        with tempfile.TemporaryDirectory() as td:
            QFileDialog.getExistingDirectory = staticmethod(
                lambda *_args, **_kwargs: td
            )
            tab.start_scan = lambda: calls.append(Path(td))
            tab.pick_input()
            app.processEvents()
            assert tab.folder == Path(td)
            assert calls == [Path(td)], calls
    finally:
        QFileDialog.getExistingDirectory = original_picker

    tab.close()
    app.processEvents()
    print("Text Cleanup UI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
