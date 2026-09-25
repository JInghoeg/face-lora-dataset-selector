"""Offscreen lifecycle smoke: closing the client must stop background Qt threads."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

import app


class CooperativeWorker(QObject):
    finished = Signal()

    def run(self):
        thread = QThread.currentThread()
        while not thread.isInterruptionRequested():
            QThread.msleep(20)
        self.finished.emit()


def start_worker(parent):
    thread = QThread(parent)
    worker = CooperativeWorker()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread._smoke_worker = worker
    thread.start()
    deadline = time.monotonic() + 2.0
    while not thread.isRunning() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert thread.isRunning()
    return thread, worker


def main():
    with tempfile.TemporaryDirectory() as td:
        os.environ["LOCALAPPDATA"] = td
        qapp = QApplication.instance() or QApplication([])
        window = app.Window()

        thread, worker = start_worker(window)
        window.auto_crop_thread = thread
        window.auto_crop_worker = worker

        assert window.shutdown_background(force=False)
        assert not thread.isRunning()

        # Exercise the actual closeEvent path as well, including the
        # Text Cleanup-owned worker and thumbnail threads.
        thread2, worker2 = start_worker(window)
        window.incremental_thread = thread2
        window.incremental_worker = worker2

        text_thread, text_worker = start_worker(window.sub)
        window.sub.thread = text_thread
        window.sub.worker = text_worker
        text_thumb, _text_thumb_worker = start_worker(window.sub)
        window.sub.thumb_threads.append(text_thumb)

        window.close()
        qapp.processEvents()
        assert not thread2.isRunning()
        assert not text_thread.isRunning()
        assert not text_thumb.isRunning()
        assert not window.isVisible()

    print("Application shutdown smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
