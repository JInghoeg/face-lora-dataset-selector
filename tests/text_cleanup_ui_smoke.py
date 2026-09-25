"""Offscreen smoke for the extracted Text Cleanup Qt presentation."""
from __future__ import annotations

import os
import sys
from pathlib import Path
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QFileDialog

from application import OperationCancelled, SelectorApplication
from core.models import TextPhoto
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
    assert tab.sort.currentData() == "优先待处理"

    # Review navigation/sorting: zero-result records stay accessible but no
    # longer occupy the front of the default review queue.
    tab.start_thumbnails = lambda *_args, **_kwargs: None

    def review_record(name, detections=0, selected=0, confidence=0.8):
        boxes = [
            [[0, 0], [20, 0], [20, 10], [0, 10]]
            for _ in range(detections)
        ]
        return TextPhoto(
            Path(name),
            0,
            0,
            boxes=boxes,
            selected=[index < selected for index in range(detections)],
            manual=[False] * detections,
            scores=[confidence] * detections,
            suggested=[index < selected for index in range(detections)],
            width=1000,
            height=1000,
        )

    tab.records = [
        review_record("00-zero.png"),
        review_record("01-detected.png", detections=1, selected=0, confidence=0.7),
        review_record("02-selected.png", detections=2, selected=1, confidence=0.9),
    ]
    tab.page = 0
    tab.refresh(False)
    assert tab.visible == [2, 1, 0], tab.visible

    original_index = tab.sort.findData("原始顺序")
    assert original_index >= 0
    tab.sort.setCurrentIndex(original_index)
    assert tab.visible == [0, 1, 2], tab.visible

    count_index = tab.sort.findData("有效检测数量：多→少")
    assert count_index >= 0
    tab.sort.setCurrentIndex(count_index)
    assert tab.visible == [2, 1, 0], tab.visible

    # Page controls sit above the review list and expose the true queue size.
    tab.records = [review_record(f"{index:03d}.png") for index in range(81)]
    tab.sort.setCurrentIndex(original_index)
    tab.page = 0
    tab.refresh(False)
    assert tab.list.count() == 80
    assert tab.next_page.isEnabled()
    tab.change_page(1)
    assert tab.page == 1
    assert tab.list.count() == 1
    assert not tab.next_page.isEnabled()

    tab.records = []
    tab.page = 0
    tab.refresh(False)

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
