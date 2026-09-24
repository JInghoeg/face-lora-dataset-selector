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

from application import OperationCancelled, SelectorApplication
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
        cancellation_exception=OperationCancelled,
    )
    assert tab.backend is backend
    assert tab.preview is not None
    assert tab.scan is not None

    # Selecting an input folder must start the real QThread scan path, not
    # merely schedule a callback. An empty temporary folder keeps this smoke
    # fast and avoids requiring OCR model inference while still exercising the
    # production worker lifecycle and visible progress state.
    original_picker = QFileDialog.getExistingDirectory
    try:
        with tempfile.TemporaryDirectory() as td:
            QFileDialog.getExistingDirectory = staticmethod(
                lambda *_args, **_kwargs: td
            )
            tab.pick_input()
            deadline = __import__("time").monotonic() + 5.0
            saw_worker = False
            while __import__("time").monotonic() < deadline:
                app.processEvents()
                if tab.thread is not None:
                    saw_worker = True
                if saw_worker and tab.thread is None:
                    break
                QThread = __import__("PySide6.QtCore", fromlist=["QThread"]).QThread
                QThread.msleep(10)

            assert tab.folder == Path(td)
            assert saw_worker, "folder selection never started Text Cleanup worker"
            assert tab.thread is None, "Text Cleanup worker did not finish"
            assert tab.records == []
            assert tab.scan.isEnabled()
            assert tab.pick_input_btn.isEnabled()
    finally:
        QFileDialog.getExistingDirectory = original_picker

    tab.close()
    app.processEvents()
    print("Text Cleanup UI smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
