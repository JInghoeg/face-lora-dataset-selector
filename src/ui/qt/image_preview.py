"""Reusable Qt image preview with editable overlay rectangles."""
from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, Qt, Signal, QRect
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
        self.setText("" if img is not None else self._tr("选择缩略图查看文字框"))
        self.boxes = boxes
        self.selected = selected
        self.manual = manual or [False] * len(boxes)
        self.start = self.now = None
        self.update()

    def set_draw_mode(self, enabled):
        self.add = bool(enabled)
        self.setCursor(Qt.CrossCursor if self.add else Qt.ArrowCursor)
        self.start = self.now = None
        self.update()

    def _point_on_image(self, point):
        if self.img is None:
            return False
        height, width = self.img.shape[:2]
        scale, dx, dy = self.scale()
        return (dx <= point.x() <= dx + width * scale
                and dy <= point.y() <= dy + height * scale)

    def _clamp_to_image(self, point):
        height, width = self.img.shape[:2]
        scale, dx, dy = self.scale()
        return (
            max(dx, min(dx + width * scale, point.x())),
            max(dy, min(dy + height * scale, point.y())),
        )

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
        if self.start is not None and self.now is not None:
            painter.setPen(QPen(QColor("#3da5ff"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(
                int(min(self.start[0], self.now[0])),
                int(min(self.start[1], self.now[1])),
                int(abs(self.now[0] - self.start[0])),
                int(abs(self.now[1] - self.start[1])),
            )
        if self.add:
            hint = self._tr("拖拽绘制修复区域")
            available = max(0, int(width * scale) - 24)
            label_width = min(available, painter.fontMetrics().horizontalAdvance(hint) + 24)
            if label_width > 45:
                label_rect = QRect(
                    int(offset_x + 12), int(offset_y + 12),
                    label_width, 31,
                )
                painter.fillRect(label_rect, QColor(17, 24, 39, 220))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(
                    label_rect.adjusted(12, 0, -4, 0),
                    Qt.AlignLeft | Qt.AlignVCenter, hint,
                )
        painter.end()

    def mousePressEvent(self, event):
        if (
            self.add and self.img is not None
            and event.button() == Qt.LeftButton
            and self._point_on_image(event.position())
        ):
            self.start = self.now = self._clamp_to_image(event.position())
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start is not None and self.img is not None:
            self.now = self._clamp_to_image(event.position())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start is None or self.img is None:
            super().mouseReleaseEvent(event)
            return
        x0, y0 = self.start
        x1, y1 = self._clamp_to_image(event.position())
        self.start = self.now = None
        if event.button() == Qt.LeftButton and abs(x1 - x0) > 8 and abs(y1 - y0) > 8:
            scale, dx, dy = self.scale()
            height, width = self.img.shape[:2]
            left = max(0, min(width, int((min(x0, x1) - dx) / scale)))
            right = max(0, min(width, int((max(x0, x1) - dx) / scale)))
            top = max(0, min(height, int((min(y0, y1) - dy) / scale)))
            bottom = max(0, min(height, int((max(y0, y1) - dy) / scale)))
            if right > left and bottom > top:
                self.drawn.emit([
                    [left, top], [right, top], [right, bottom], [left, bottom],
                ])
        self.update()
        event.accept()
