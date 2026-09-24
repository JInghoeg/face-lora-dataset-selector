"""Reusable Qt image preview with editable overlay rectangles."""
from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel


class ImagePreview(QLabel):
    drawn = Signal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(520, 400)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#222;color:#ddd")
        self.img = None
        self.boxes = []
        self.selected = []
        self.manual = []
        self.add = False
        self.start = None
        self.now = None
        self.retranslate()

    @staticmethod
    def _tr(source):
        return QCoreApplication.translate("ImagePreview", source)

    def retranslate(self):
        if self.img is None:
            self.setText(self._tr("选择缩略图查看文字框"))

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            self.retranslate()
        super().changeEvent(event)

    def set_data(self, img, boxes, selected, manual=None):
        self.img = img
        self.boxes = boxes
        self.selected = selected
        self.manual = manual or [False] * len(boxes)
        self.start = self.now = None
        self.update()

    def scale(self):
        if self.img is None:
            return 1, 0, 0
        height, width = self.img.shape[:2]
        scale = min(self.width() / width, self.height() / height)
        return (
            scale,
            (self.width() - width * scale) / 2,
            (self.height() - height * scale) / 2,
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.img is None:
            return
        height, width = self.img.shape[:2]
        rgb = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
        pixmap = QPixmap.fromImage(
            QImage(
                rgb.data,
                width,
                height,
                rgb.strides[0],
                QImage.Format_RGB888,
            ).copy()
        )
        scale, offset_x, offset_y = self.scale()
        painter = QPainter(self)
        painter.drawPixmap(
            int(offset_x),
            int(offset_y),
            int(width * scale),
            int(height * scale),
            pixmap,
        )
        for box, selected, manual in zip(self.boxes, self.selected, self.manual):
            points = np.asarray(box)
            painter.setPen(
                QPen(
                    QColor(
                        "#32e675"
                        if selected
                        else ("#ffb000" if manual else "#999")
                    ),
                    2,
                )
            )
            painter.drawRect(
                int(offset_x + points[:, 0].min() * scale),
                int(offset_y + points[:, 1].min() * scale),
                int((points[:, 0].max() - points[:, 0].min()) * scale),
                int((points[:, 1].max() - points[:, 1].min()) * scale),
            )
        if self.start and self.now:
            painter.setPen(QPen(QColor("#3da5ff"), 2))
            painter.drawRect(
                int(self.start[0]),
                int(self.start[1]),
                int(self.now[0] - self.start[0]),
                int(self.now[1] - self.start[1]),
            )
        painter.end()

    def mousePressEvent(self, event):
        if self.add and self.img is not None:
            self.start = self.now = (event.position().x(), event.position().y())
            self.update()

    def mouseMoveEvent(self, event):
        if self.start:
            self.now = (event.position().x(), event.position().y())
            self.update()

    def mouseReleaseEvent(self, event):
        if not self.start or self.img is None:
            return
        x0, y0 = map(min, zip(self.start, self.now))
        x1, y1 = map(max, zip(self.start, self.now))
        scale, offset_x, offset_y = self.scale()
        self.start = self.now = None
        if x1 - x0 > 8 and y1 - y0 > 8:
            self.drawn.emit(
                [
                    [int((x0 - offset_x) / scale), int((y0 - offset_y) / scale)],
                    [int((x1 - offset_x) / scale), int((y0 - offset_y) / scale)],
                    [int((x1 - offset_x) / scale), int((y1 - offset_y) / scale)],
                    [int((x0 - offset_x) / scale), int((y1 - offset_y) / scale)],
                ]
            )
        self.update()
