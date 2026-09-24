"""Long-operation control smoke: cancellation, progress and CPU budget."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

import app
from application import SelectorApplication
from core.cancellation import OperationCancelled, check_cancelled
from core.models import Photo
from infrastructure.runtime_tuning import analysis_thread_budget


class FakeRefreshResult:
    had_v3_cache = False
    changed_count = 0
    added_count = 0
    modified_count = 0
    deleted_count = 0
    unchanged_count = 0
    records = []


class FakeBackend:
    def refresh_dataset(self, folder, status=None, progress=None, cancelled=None):
        status = status or (lambda _message: None)
        progress = progress or (lambda _current, _total, _name: None)
        status("working")
        for i in range(1, 500):
            check_cancelled(cancelled)
            progress(i, 500, f"item-{i}.jpg")
            QThread.msleep(5)
        return FakeRefreshResult()


def cancellation_smoke(qapp):
    old_backend = app.BACKEND
    app.BACKEND = FakeBackend()
    try:
        thread = QThread()
        worker = app.Analyzer(Path("."))
        worker.moveToThread(thread)
        state = {"finished": 0, "cancelled": 0, "failed": 0}
        worker.finished.connect(lambda _value: state.__setitem__("finished", state["finished"] + 1))
        worker.cancelled.connect(lambda: state.__setitem__("cancelled", state["cancelled"] + 1))
        worker.failed.connect(lambda _error: state.__setitem__("failed", state["failed"] + 1))
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.start(QThread.Priority.LowPriority)

        deadline = time.monotonic() + 2.0
        while not thread.isRunning() and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert thread.isRunning()

        time.sleep(0.08)
        thread.requestInterruption()
        deadline = time.monotonic() + 3.0
        while thread.isRunning() and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        qapp.processEvents()

        assert not thread.isRunning()
        assert state == {"finished": 0, "cancelled": 1, "failed": 0}, state
        worker.deleteLater()
        thread.deleteLater()
    finally:
        app.BACKEND = old_backend


def export_progress_smoke(root: Path):
    backend = SelectorApplication()
    records = []
    for index in range(3):
        path = root / f"source-{index}.png"
        Image.new("RGB", (32, 32), (40 + index, 50, 60)).save(path)
        photo = Photo(path)
        photo.status = "推荐"
        records.append(photo)
    rejected = root / "rejected.png"
    Image.new("RGB", (32, 32), (1, 2, 3)).save(rejected)
    skipped = Photo(rejected)
    skipped.status = "淘汰"
    records.append(skipped)

    events = []
    dst = root / "export"
    result = backend.export_recommended(
        records,
        dst,
        progress=lambda current, total, name: events.append((current, total, name)),
    )
    assert result.written == 3
    assert [item[:2] for item in events] == [(1, 3), (2, 3), (3, 3)], events
    assert len(list(dst.glob("*.png"))) == 3


def main():
    qapp = QApplication.instance() or QApplication([])
    budget = analysis_thread_budget()
    assert 1 <= budget <= 6, budget
    cancellation_smoke(qapp)
    with tempfile.TemporaryDirectory() as td:
        export_progress_smoke(Path(td))
    print(f"Operation control smoke OK; analysis thread budget={budget}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
