"""Reusable thumbnail worker for Qt presentation surfaces."""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage


def _path_key(path):
    return str(Path(path).resolve()).casefold()


class ThumbnailWorker(QObject):
    ready = Signal(int, int, object)
    finished = Signal(int)

    def __init__(self, token, items, cache_dir):
        super().__init__()
        self.token = token
        self.items = items
        self.cache_dir = Path(cache_dir)

    def disk_path(self, photo):
        digest = hashlib.sha256(
            f"{_path_key(photo.path)}:{photo.file_size}:{photo.mtime_ns}".encode()
        ).hexdigest()
        return self.cache_dir / f"{digest}.jpg"

    def run(self):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            for index, photo in self.items:
                if QThread.currentThread().isInterruptionRequested():
                    break
                cache = self.disk_path(photo)
                try:
                    with Image.open(cache if cache.exists() else photo.path) as image:
                        image = image.convert("RGB")
                        image.thumbnail((150, 150), Image.Resampling.LANCZOS)
                        canvas = Image.new("RGB", (150, 150), (30, 30, 30))
                        canvas.paste(
                            image,
                            ((150 - image.width) // 2, (150 - image.height) // 2),
                        )
                        if not cache.exists():
                            canvas.save(cache, "JPEG", quality=85, optimize=True)
                        data = canvas.tobytes()
                        qimage = QImage(
                            data,
                            150,
                            150,
                            150 * 3,
                            QImage.Format_RGB888,
                        ).copy()
                        self.ready.emit(self.token, index, qimage)
                except Exception:
                    pass
        finally:
            self.finished.emit(self.token)
