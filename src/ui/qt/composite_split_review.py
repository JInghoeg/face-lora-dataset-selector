"""Production Composite Split review dialog.

Presentation follows the user-accepted v0.4 prototype while keeping Composite
business semantics in the application/feature layers.  The current editable
rectangle reuses AutoCropROIWidget; Composite adds only multi-box selection,
direct-draw creation, and non-selected outlines around that shared editor.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
from PIL import Image, ImageOps
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QPointF,
    QRectF,
    Qt,
    QSize,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .auto_crop_review import AutoCropROIWidget


def _load_fluent():
    try:
        from qfluentwidgets import (
            CaptionLabel,
            FluentIcon,
            PrimaryPushButton,
            PushButton,
            SimpleCardWidget,
            StrongBodyLabel,
            Theme,
            TransparentPushButton,
            TransparentToolButton,
            isDarkTheme,
            setTheme,
        )
    except ImportError:
        return None
    return {
        "CaptionLabel": CaptionLabel,
        "FluentIcon": FluentIcon,
        "PrimaryPushButton": PrimaryPushButton,
        "PushButton": PushButton,
        "SimpleCardWidget": SimpleCardWidget,
        "StrongBodyLabel": StrongBodyLabel,
        "Theme": Theme,
        "TransparentPushButton": TransparentPushButton,
        "TransparentToolButton": TransparentToolButton,
        "isDarkTheme": isDarkTheme,
        "setTheme": setTheme,
    }


class CompositeROIWidget(AutoCropROIWidget):
    """Multi-box shell around the proven Auto Crop single-ROI editor."""

    boxSelected = Signal(int)
    boxCreated = Signal(object)

    OUTLINE_COLORS = ("#5dade2", "#58d68d", "#af7ac5", "#f5b041", "#ec7063")

    def __init__(self, parent=None):
        # AutoCropROIWidget.__init__ calls self.set_theme(), so Composite-owned
        # state used by the override must exist before entering the parent.
        self.boxes = []
        self.selected_index = -1
        self._other_outlines = []
        self._drawing = False
        self._draw_start = None
        self._draw_current = None
        super().__init__(parent)
        self._draft = pg.PlotCurveItem(
            [],
            [],
            pen=pg.mkPen("#60cdff", width=2, style=Qt.DashLine),
        )
        self.view.addItem(self._draft)
        self._draft.setVisible(False)
        self.roi.setPen(pg.mkPen("#60cdff", width=3))
        self.canvas.viewport().installEventFilter(self)

    def set_theme(self, dark):
        super().set_theme(dark)
        self._refresh_outlines()

    def set_boxes(self, bgr, boxes, selected=0, baselines=None):
        self.boxes = [list(map(int, box)) for box in boxes]
        baselines = (
            [list(map(int, box)) for box in baselines]
            if baselines is not None
            else [list(box) for box in self.boxes]
        )
        if self.boxes:
            self.selected_index = max(0, min(int(selected), len(self.boxes) - 1))
            baseline = (
                baselines[self.selected_index]
                if self.selected_index < len(baselines)
                else self.boxes[self.selected_index]
            )
            super().set_data(
                bgr,
                self.boxes[self.selected_index],
                baseline,
            )
            # Composite reset is a button action; avoid a second dashed box
            # competing with the multi-box outlines.
            self.auto_outline.setVisible(False)
            self.roi.setVisible(True)
        else:
            self.selected_index = -1
            self._set_image_only(bgr)
        self._refresh_outlines()

    def _set_image_only(self, bgr):
        self._loading = True
        try:
            self.image = bgr
            if bgr is None or not getattr(bgr, "size", 0):
                self.image_item.clear()
                self.image_size = (0, 0)
                self.roi.setVisible(False)
                self.auto_outline.setVisible(False)
                return
            h, w = bgr.shape[:2]
            self.image_size = (w, h)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            self.image_item.setImage(rgb, autoLevels=False, levels=(0, 255))
            pad_x = max(16.0, w * 0.04)
            pad_y = max(16.0, h * 0.04)
            self._fit_padding = (pad_x, pad_y)
            self._fit_source()
            self.roi.setVisible(False)
            self.auto_outline.setVisible(False)
        finally:
            self._loading = False
        QTimer.singleShot(0, self._fit_source)

    def _ensure_outlines(self, count):
        while len(self._other_outlines) < count:
            curve = pg.PlotCurveItem([], [])
            self.view.addItem(curve)
            self._other_outlines.append(curve)
        while len(self._other_outlines) > count:
            curve = self._other_outlines.pop()
            self.view.removeItem(curve)

    def _refresh_outlines(self):
        visible = [
            (index, box)
            for index, box in enumerate(self.boxes)
            if index != self.selected_index
        ]
        self._ensure_outlines(len(visible))
        for slot, (index, box) in enumerate(visible):
            x0, y0, x1, y1 = box
            curve = self._other_outlines[slot]
            color = self.OUTLINE_COLORS[index % len(self.OUTLINE_COLORS)]
            curve.setPen(pg.mkPen(color, width=2))
            curve.setData(
                [x0, x1, x1, x0, x0],
                [y0, y0, y1, y1, y0],
            )
            curve.setVisible(True)

    def eventFilter(self, watched, event):
        if watched is not self.canvas.viewport():
            return super().eventFilter(watched, event)
        if not self.image_size[0] or not self.image_size[1]:
            return False

        event_type = event.type()
        if event_type not in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            return False

        scene_point = self.canvas.mapToScene(event.position().toPoint())
        view_point = self.view.mapSceneToView(scene_point)
        x = float(view_point.x())
        y = float(view_point.y())
        w, h = self.image_size
        inside_image = 0 <= x <= w and 0 <= y <= h

        if event_type == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.LeftButton or not inside_image:
                return False
            for index, box in enumerate(self.boxes):
                x0, y0, x1, y1 = box
                if x0 <= x <= x1 and y0 <= y <= y1:
                    if index != self.selected_index:
                        self.boxSelected.emit(index)
                        return True
                    # Current ROI keeps its native Auto Crop move/resize path.
                    return False
            self._drawing = True
            self._draw_start = QPointF(x, y)
            self._draw_current = QPointF(x, y)
            self._update_draft()
            return True

        if event_type == QEvent.Type.MouseMove and self._drawing:
            self._draw_current = QPointF(
                min(max(x, 0.0), float(w)),
                min(max(y, 0.0), float(h)),
            )
            self._update_draft()
            return True

        if (
            event_type == QEvent.Type.MouseButtonRelease
            and self._drawing
            and event.button() == Qt.LeftButton
        ):
            self._drawing = False
            end = self._draw_current or QPointF(x, y)
            start = self._draw_start or end
            self._draft.setVisible(False)
            self._draw_start = None
            self._draw_current = None
            x0, x1 = sorted((start.x(), end.x()))
            y0, y1 = sorted((start.y(), end.y()))
            if x1 - x0 >= 24 and y1 - y0 >= 24:
                self.boxCreated.emit(
                    self.normalized_box([x0, y0, x1, y1], self.image_size)
                )
            return True

        return False

    def _update_draft(self):
        if self._draw_start is None or self._draw_current is None:
            self._draft.setVisible(False)
            return
        x0, x1 = sorted((self._draw_start.x(), self._draw_current.x()))
        y0, y1 = sorted((self._draw_start.y(), self._draw_current.y()))
        self._draft.setData(
            [x0, x1, x1, x0, x0],
            [y0, y0, y1, y1, y0],
        )
        self._draft.setVisible(True)


class CompositeCandidateList(QListWidget):
    DEFAULT_HEIGHT = 106

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CompositeCandidateList")
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setIconSize(QSize(72, 48))
        self.setGridSize(QSize(148, 104))
        self.setSpacing(4)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setMinimumHeight(self.DEFAULT_HEIGHT)
        self.setMaximumHeight(self.DEFAULT_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(self.DEFAULT_HEIGHT)
        return hint


class CompositeOutputGrid(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CompositeOutputGrid")
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSpacing(8)
        self.setWordWrap(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self):
        width = max(1, self.viewport().width())
        cols = 2 if width >= 520 else 1
        cell_w = max(250, int((width - 24) / cols))
        cell_h = 292
        self.setIconSize(QSize(cell_w - 24, 210))
        self.setGridSize(QSize(cell_w, cell_h))
        for row in range(self.count()):
            self.item(row).setSizeHint(QSize(cell_w - 8, cell_h - 8))


class CompositeSplitReviewDialog(QDialog):
    """Review/edit Composite proposals without changing detector semantics."""

    _preferred_theme = "light"

    def __init__(
        self,
        backend,
        records,
        changed,
        accept_materialized,
        thumbnail_cache,
        parent=None,
        event_logger=None,
        focus_record=None,
        redetect_current=None,
    ):
        super().__init__(parent)
        self.backend = backend
        self.changed = changed
        self.accept_materialized = accept_materialized
        self.thumbnail_cache = Path(thumbnail_cache)
        self._event_logger = event_logger or (lambda _name, **_fields: None)
        self.redetect_current_callback = redetect_current
        self.records = [
            record for record in records if record.composite_proposal is not None
        ]
        if (
            focus_record is not None
            and focus_record.composite_proposal is not None
            and focus_record not in self.records
        ):
            self.records.append(focus_record)

        self.current = -1
        self.selected_box = 0
        self.current_image = None
        self.output_keep = {}
        self._window_drag_offset = None
        self._fluent = _load_fluent()
        self._initial_global_dark = (
            bool(self._fluent["isDarkTheme"]()) if self._fluent else False
        )
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if self._preferred_theme == "dark"
                else self._fluent["Theme"].LIGHT
            )

        self.setObjectName("CompositeSplitReviewDialog")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.resize(1580, 940)
        self._build_ui()
        self.retranslate()
        self.apply_theme(self._preferred_theme)
        self.reload(select_record=focus_record)

    @staticmethod
    def _tr(source):
        return QCoreApplication.translate("CompositeSplitReviewDialog", source)

    @staticmethod
    def _record_key(record):
        return record.sample_id or str(record.path.resolve()).casefold()

    @staticmethod
    def _pixmap_from_bgr(img):
        if img is None or not getattr(img, "size", 0):
            return QPixmap()
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data,
            w,
            h,
            rgb.strides[0],
            QImage.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(image)

    @staticmethod
    def _load_image(path):
        with Image.open(path) as source:
            try:
                source.seek(0)
            except EOFError:
                pass
            source = ImageOps.exif_transpose(source).convert("RGB")
            rgb = np.asarray(source)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 58:
            self._window_drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._window_drag_offset is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._window_drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._window_drag_offset = None
        super().mouseReleaseEvent(event)

    def _button(self, kind):
        if self._fluent:
            mapping = {
                "primary": self._fluent["PrimaryPushButton"],
                "secondary": self._fluent["PushButton"],
                "weak": self._fluent["TransparentPushButton"],
            }
            return mapping[kind]("")
        return QPushButton("")

    def _label(self, strong=False):
        if self._fluent:
            return (
                self._fluent["StrongBodyLabel"]("")
                if strong
                else self._fluent["CaptionLabel"]("")
            )
        label = QLabel("")
        if strong:
            label.setStyleSheet("font-weight:700;")
        return label

    def _card(self):
        return self._fluent["SimpleCardWidget"]() if self._fluent else QWidget()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        self.header_title = self._label(strong=True)
        if self._fluent:
            self.header_title.setStyleSheet("font-size:20px;")
        header.addWidget(self.header_title)
        header.addStretch(1)
        self.header_state = self._label()
        header.addWidget(self.header_state)

        if self._fluent:
            self.theme_button = self._fluent["TransparentToolButton"](
                self._fluent["FluentIcon"].QUIET_HOURS
            )
            self.theme_button.setFixedSize(34, 30)
            self.theme_button.clicked.connect(self.toggle_theme)
            header.addWidget(self.theme_button)
            self.top_close = self._fluent["TransparentToolButton"](
                self._fluent["FluentIcon"].CLOSE
            )
            self.top_close.setFixedSize(34, 30)
        else:
            self.theme_button = None
            self.top_close = QPushButton("×")
            self.top_close.setFixedSize(34, 30)
        self.top_close.clicked.connect(self.accept)
        header.addWidget(self.top_close)
        root.addLayout(header)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setObjectName("CompositeMainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setOpaqueResize(True)
        self.main_splitter.splitterMoved.connect(
            lambda _pos, _index: self._sync_candidate_expansion()
        )

        self.work_splitter = QSplitter(Qt.Horizontal)
        self.work_splitter.setObjectName("CompositeWorkSplitter")
        self.work_splitter.setChildrenCollapsible(False)
        self.work_splitter.setHandleWidth(8)
        self.work_splitter.setOpaqueResize(True)

        self.source_card = self._card()
        source_layout = QVBoxLayout(self.source_card)
        source_layout.setContentsMargins(10, 10, 10, 10)
        source_layout.setSpacing(7)

        source_head = QHBoxLayout()
        self.source_title = self._label(strong=True)
        source_head.addWidget(self.source_title)
        self.mode_label = self._label()
        source_head.addWidget(self.mode_label)
        source_head.addStretch(1)

        self.redetect_button = self._button("secondary")
        self.redetect_button.clicked.connect(self.redetect_current)
        source_head.addWidget(self.redetect_button)
        self.reset_button = self._button("weak")
        self.reset_button.clicked.connect(self.reset_current_box)
        source_head.addWidget(self.reset_button)
        self.delete_button = self._button("weak")
        self.delete_button.clicked.connect(self.delete_current_box)
        source_head.addWidget(self.delete_button)
        source_layout.addLayout(source_head)

        self.source_hint = self._label()
        source_layout.addWidget(self.source_hint)
        self.roi_preview = CompositeROIWidget()
        self.roi_preview.regionChanged.connect(self.roi_changed)
        self.roi_preview.regionChangeFinished.connect(self.roi_finished)
        self.roi_preview.boxSelected.connect(self.select_box)
        self.roi_preview.boxCreated.connect(self.create_box)
        source_layout.addWidget(self.roi_preview, 1)
        self.source_meta = self._label()
        source_layout.addWidget(self.source_meta)
        self.work_splitter.addWidget(self.source_card)

        self.outputs_card = self._card()
        outputs_layout = QVBoxLayout(self.outputs_card)
        outputs_layout.setContentsMargins(10, 10, 10, 10)
        outputs_layout.setSpacing(7)
        outputs_head = QHBoxLayout()
        self.outputs_title = self._label(strong=True)
        outputs_head.addWidget(self.outputs_title)
        self.output_count = self._label()
        outputs_head.addWidget(self.output_count)
        outputs_head.addStretch(1)
        outputs_layout.addLayout(outputs_head)
        self.outputs_hint = self._label()
        outputs_layout.addWidget(self.outputs_hint)
        self.outputs = CompositeOutputGrid()
        self.outputs.itemClicked.connect(self.output_clicked)
        self.outputs.itemChanged.connect(self.output_selection_changed)
        outputs_layout.addWidget(self.outputs, 1)
        self.work_splitter.addWidget(self.outputs_card)
        self.work_splitter.setStretchFactor(0, 3)
        self.work_splitter.setStretchFactor(1, 2)
        self.work_splitter.setSizes([900, 600])
        self.main_splitter.addWidget(self.work_splitter)

        self.candidate_card = self._card()
        candidate_layout = QVBoxLayout(self.candidate_card)
        candidate_layout.setContentsMargins(8, 6, 8, 8)
        candidate_layout.setSpacing(4)
        candidate_head = QHBoxLayout()
        self.candidates_title = self._label(strong=True)
        candidate_head.addWidget(self.candidates_title)
        self.candidate_counts = self._label()
        candidate_head.addWidget(self.candidate_counts)
        self.expand_hint = self._label()
        candidate_head.addWidget(self.expand_hint)
        candidate_head.addStretch(1)
        candidate_layout.addLayout(candidate_head)

        self.items = CompositeCandidateList()
        self.items.currentRowChanged.connect(self.show_row)
        candidate_layout.addWidget(self.items)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.accept_button = self._button("primary")
        self.accept_button.setMinimumHeight(42)
        self.accept_button.clicked.connect(lambda: self.set_decision("accepted"))
        actions.addWidget(self.accept_button)
        self.reject_button = self._button("secondary")
        self.reject_button.setMinimumHeight(40)
        self.reject_button.clicked.connect(lambda: self.set_decision("rejected"))
        actions.addWidget(self.reject_button)
        self.pending_button = self._button("weak")
        self.pending_button.setMinimumHeight(40)
        self.pending_button.clicked.connect(lambda: self.set_decision("pending"))
        actions.addWidget(self.pending_button)
        actions.addStretch(1)
        self.close_button = self._button("weak")
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)
        actions.addWidget(QSizeGrip(self))
        candidate_layout.addLayout(actions)

        self.main_splitter.addWidget(self.candidate_card)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        root.addWidget(self.main_splitter, 1)
        QTimer.singleShot(0, self._apply_initial_candidate_size)

    def _apply_initial_candidate_size(self):
        sizes = self.main_splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        target = 208
        self.main_splitter.setSizes([max(1, total - target), target])
        self._default_candidate_pane_height = self.main_splitter.sizes()[1]
        self.items.setMaximumHeight(CompositeCandidateList.DEFAULT_HEIGHT)

    def _sync_candidate_expansion(self):
        sizes = self.main_splitter.sizes()
        if len(sizes) < 2:
            return
        default_height = getattr(
            self,
            "_default_candidate_pane_height",
            sizes[1],
        )
        expanded = sizes[1] > default_height + 8
        self.items.setMaximumHeight(
            16777215 if expanded else CompositeCandidateList.DEFAULT_HEIGHT
        )
        self.items.updateGeometry()

    def _proposal(self, record):
        return record.composite_proposal

    def _ensure_baselines(self, proposal):
        boxes = [list(map(int, box)) for box in proposal.output_boxes]
        baseline = getattr(proposal, "baseline_boxes", None)
        if not isinstance(baseline, list):
            baseline = []
        baseline = [list(map(int, box)) for box in baseline]
        if len(baseline) < len(boxes):
            baseline.extend(
                [list(box) for box in boxes[len(baseline) :]]
            )
        elif len(baseline) > len(boxes):
            baseline = baseline[: len(boxes)]
        proposal.baseline_boxes = baseline
        return proposal.baseline_boxes

    def _thumbnail(self, path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaled(
            self.items.iconSize(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

    def _candidate_item_text(self, record):
        proposal = self._proposal(record)
        mode = self._tr("拆分") if proposal.mode == "split_people" else self._tr("群组")
        return self._tr("{index:02d} · {mode} · {count} 输出").format(
            index=self.records.index(record) + 1,
            mode=mode,
            count=len(proposal.output_boxes),
        )

    def _decision_text(self, decision):
        return {
            "accepted": self._tr("已接受"),
            "rejected": self._tr("已拒绝"),
            "pending": self._tr("待定"),
        }.get(decision, str(decision))

    def reload(self, select_record=None):
        current_record = None
        if 0 <= self.current < len(self.records):
            current_record = self.records[self.current]
        target_record = select_record or current_record

        self.items.blockSignals(True)
        self.items.clear()
        for row, record in enumerate(self.records):
            proposal = self._proposal(record)
            item = QListWidgetItem(
                QIcon(self._thumbnail(record.path)),
                self._candidate_item_text(record),
            )
            item.setData(Qt.UserRole, row)
            item.setData(Qt.UserRole + 1, proposal.decision)
            item.setSizeHint(QSize(142, 100))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setToolTip(
                self._tr("候选 {index:02d} · {state}").format(
                    index=row + 1,
                    state=self._decision_text(proposal.decision),
                )
            )
            self.items.addItem(item)
        self.items.blockSignals(False)
        self._update_candidate_counts()
        self._apply_candidate_state_colors()

        if not self.records:
            self.current = -1
            self._clear_current()
            return
        try:
            target = self.records.index(target_record) if target_record else 0
        except ValueError:
            target = 0
        self.items.setCurrentRow(target)
        self.show_row(target)

    def _clear_current(self):
        self.header_state.setText("")
        self.mode_label.setText("")
        self.source_meta.setText("")
        self.output_count.setText(self._tr("暂无输出"))
        self.outputs.clear()
        self.current_image = None
        self.roi_preview.set_boxes(None, [], 0, [])
        self.accept_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.redetect_button.setVisible(False)

    def _update_candidate_counts(self):
        accepted = rejected = pending = 0
        for record in self.records:
            decision = getattr(self._proposal(record), "decision", "pending")
            if decision == "accepted":
                accepted += 1
            elif decision == "rejected":
                rejected += 1
            else:
                pending += 1
        self.candidate_counts.setText(
            self._tr("待定 {pending} · 接受 {accepted} · 拒绝 {rejected}").format(
                pending=pending,
                accepted=accepted,
                rejected=rejected,
            )
        )

    def _apply_candidate_state_colors(self):
        dark = self._preferred_theme == "dark"
        palette = (
            {
                "accepted": QColor("#23382b"),
                "pending": QColor("#3a3020"),
                "rejected": QColor("#3a2428"),
            }
            if dark
            else {
                "accepted": QColor("#dcefe2"),
                "pending": QColor("#ffe8bd"),
                "rejected": QColor("#efd6d8"),
            }
        )
        for row in range(self.items.count()):
            item = self.items.item(row)
            state = item.data(Qt.UserRole + 1) or "pending"
            item.setData(Qt.BackgroundRole, palette.get(state, palette["pending"]))

    def show_row(self, row):
        if row < 0 or row >= len(self.records):
            return
        self.current = row
        record = self.records[row]
        proposal = self._proposal(record)
        self._ensure_baselines(proposal)
        try:
            self.current_image = self._load_image(record.path)
        except Exception:
            self.current_image = None
        self.selected_box = min(
            self.selected_box,
            max(0, len(proposal.output_boxes) - 1),
        )
        if not proposal.output_boxes:
            self.selected_box = 0

        record_key = self._record_key(record)
        keep = self.output_keep.get(record_key)
        if not isinstance(keep, list) or len(keep) != len(proposal.output_boxes):
            keep = [True] * len(proposal.output_boxes)
            self.output_keep[record_key] = keep

        self._render_source()
        self._render_outputs()
        self._update_current_labels()
        self._update_tool_state()

    def _render_source(self):
        if self.current < 0:
            return
        proposal = self._proposal(self.records[self.current])
        baselines = self._ensure_baselines(proposal)
        self.roi_preview.set_boxes(
            self.current_image,
            proposal.output_boxes,
            self.selected_box,
            baselines,
        )

    def _render_outputs(self):
        if self.current < 0:
            return
        record = self.records[self.current]
        proposal = self._proposal(record)
        keep = self.output_keep.setdefault(
            self._record_key(record),
            [True] * len(proposal.output_boxes),
        )
        self.outputs.blockSignals(True)
        self.outputs.clear()
        if self.current_image is not None:
            h, w = self.current_image.shape[:2]
            for index, box in enumerate(proposal.output_boxes):
                x0, y0, x1, y1 = AutoCropROIWidget.normalized_box(box, (w, h))
                crop = self.current_image[y0:y1, x0:x1]
                pixmap = self._pixmap_from_bgr(crop).scaled(
                    self.outputs.iconSize(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                state = self._tr("推荐") if keep[index] else self._tr("淘汰")
                item = QListWidgetItem(
                    QIcon(pixmap),
                    self._tr("输出 {index} · {state}").format(
                        index=index + 1,
                        state=state,
                    )
                    + f"\n{x1 - x0} × {y1 - y0}",
                )
                item.setData(Qt.UserRole, index)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if keep[index] else Qt.Unchecked)
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
                self.outputs.addItem(item)
        self.outputs.blockSignals(False)
        self.outputs.reflow()
        if self.outputs.count():
            self.outputs.setCurrentRow(
                min(self.selected_box, self.outputs.count() - 1)
            )

    def _update_current_labels(self):
        if self.current < 0:
            return
        record = self.records[self.current]
        proposal = self._proposal(record)
        source_label = (
            self._tr("手动")
            if getattr(proposal, "manual_triggered", False)
            else self._tr("自动")
        )
        self.header_state.setText(
            self._tr("{current:02d} / {total} · {state}").format(
                current=self.current + 1,
                total=len(self.records),
                state=self._decision_text(proposal.decision),
            )
        )
        self.mode_label.setText(
            self._tr("{source} · {count} 输出").format(
                source=source_label,
                count=len(proposal.output_boxes),
            )
        )
        if proposal.output_boxes:
            self.source_meta.setText(
                self._tr("{name} · 当前框 {current} / {count}").format(
                    name=record.path.name,
                    current=self.selected_box + 1,
                    count=len(proposal.output_boxes),
                )
            )
        else:
            self.source_meta.setText(
                self._tr("{name} · 暂无拆分框").format(name=record.path.name)
            )
        keep = self.output_keep.get(self._record_key(record), [])
        if keep:
            self.output_count.setText(
                self._tr("保留 {kept}/{total} · 当前 {current}").format(
                    kept=sum(bool(value) for value in keep),
                    total=len(keep),
                    current=min(self.selected_box + 1, len(keep)),
                )
            )
        else:
            self.output_count.setText(self._tr("暂无输出"))

    def _update_tool_state(self):
        if self.current < 0:
            return
        proposal = self._proposal(self.records[self.current])
        has_box = bool(proposal.output_boxes)
        self.accept_button.setEnabled(has_box)
        self.reset_button.setVisible(True)
        self.delete_button.setVisible(True)
        self.reset_button.setEnabled(has_box)
        self.delete_button.setEnabled(has_box)
        self.redetect_button.setVisible(
            bool(getattr(proposal, "manual_triggered", False))
        )
        self.redetect_button.setEnabled(
            self.redetect_current_callback is not None
        )

    def select_box(self, index):
        if self.current < 0:
            return
        proposal = self._proposal(self.records[self.current])
        if not (0 <= int(index) < len(proposal.output_boxes)):
            return
        self.selected_box = int(index)
        self._render_source()
        self.outputs.blockSignals(True)
        self.outputs.setCurrentRow(self.selected_box)
        self.outputs.blockSignals(False)
        self._update_current_labels()

    def output_clicked(self, item):
        index = item.data(Qt.UserRole)
        if isinstance(index, int):
            self.select_box(index)

    def roi_changed(self, box):
        if self.current < 0:
            return
        proposal = self._proposal(self.records[self.current])
        if not (0 <= self.selected_box < len(proposal.output_boxes)):
            return
        proposal.output_boxes[self.selected_box] = list(map(int, box))
        self._render_outputs()
        self._refresh_current_candidate_item()
        self._update_current_labels()

    def roi_finished(self, box):
        self.roi_changed(box)
        self.changed()

    def create_box(self, box):
        if self.current < 0:
            return
        proposal = self._proposal(self.records[self.current])
        baseline = self._ensure_baselines(proposal)
        new_box = list(map(int, box))
        proposal.output_boxes.append(new_box)
        baseline.append(list(new_box))
        proposal.baseline_boxes = baseline
        record_key = self._record_key(self.records[self.current])
        keep = self.output_keep.setdefault(record_key, [])
        keep.append(True)
        self.selected_box = len(proposal.output_boxes) - 1
        self._render_source()
        self._render_outputs()
        self._refresh_current_candidate_item()
        self._update_current_labels()
        self._update_tool_state()
        self.changed()

    def reset_current_box(self):
        if self.current < 0:
            return
        proposal = self._proposal(self.records[self.current])
        baseline = self._ensure_baselines(proposal)
        if not (0 <= self.selected_box < len(proposal.output_boxes)):
            return
        proposal.output_boxes[self.selected_box] = list(
            baseline[self.selected_box]
        )
        self._render_source()
        self._render_outputs()
        self._update_current_labels()
        self.changed()

    def delete_current_box(self):
        if self.current < 0:
            return
        record = self.records[self.current]
        proposal = self._proposal(record)
        if not (0 <= self.selected_box < len(proposal.output_boxes)):
            return
        baseline = self._ensure_baselines(proposal)
        del proposal.output_boxes[self.selected_box]
        if self.selected_box < len(baseline):
            del baseline[self.selected_box]
        proposal.baseline_boxes = baseline
        keep = self.output_keep.setdefault(self._record_key(record), [])
        if self.selected_box < len(keep):
            del keep[self.selected_box]
        self.selected_box = min(
            self.selected_box,
            max(0, len(proposal.output_boxes) - 1),
        )
        self._render_source()
        self._render_outputs()
        self._refresh_current_candidate_item()
        self._update_current_labels()
        self._update_tool_state()
        self.changed()

    def redetect_current(self):
        if self.current < 0 or self.redetect_current_callback is None:
            return
        record = self.records[self.current]
        proposal = self.redetect_current_callback(record)
        if proposal is False:
            return
        if proposal is None:
            proposal = self.backend.make_composite_proposal(
                mode="split_people",
                output_boxes=[],
                baseline_boxes=[],
                manual_triggered=True,
                decision="pending",
                detail="",
            )
        else:
            proposal.manual_triggered = True
            proposal.baseline_boxes = [
                list(box) for box in proposal.output_boxes
            ]
            proposal.decision = "pending"
        record.composite_proposal = proposal
        record.composite_scan_version = self.backend.composite_proposal_version
        self.output_keep[self._record_key(record)] = [
            True
        ] * len(proposal.output_boxes)
        self.selected_box = 0
        self.changed()
        self.reload(select_record=record)

    def output_selection_changed(self, item):
        if self.current < 0:
            return
        index = item.data(Qt.UserRole)
        if not isinstance(index, int):
            return
        record = self.records[self.current]
        proposal = self._proposal(record)
        keep = self.output_keep.setdefault(
            self._record_key(record),
            [True] * len(proposal.output_boxes),
        )
        if not (0 <= index < len(keep)):
            return
        keep[index] = item.checkState() == Qt.Checked
        self.outputs.blockSignals(True)
        state = self._tr("推荐") if keep[index] else self._tr("淘汰")
        lines = item.text().splitlines()
        if lines:
            lines[0] = self._tr("输出 {index} · {state}").format(
                index=index + 1,
                state=state,
            )
            item.setText("\n".join(lines))
        self.outputs.blockSignals(False)
        self._update_current_labels()

    def _refresh_current_candidate_item(self):
        if not (0 <= self.current < self.items.count()):
            return
        item = self.items.item(self.current)
        record = self.records[self.current]
        proposal = self._proposal(record)
        item.setText(self._candidate_item_text(record))
        item.setData(Qt.UserRole + 1, proposal.decision)
        self._apply_candidate_state_colors()
        self._update_candidate_counts()

    def set_decision(self, value):
        if self.current < 0:
            return
        record = self.records[self.current]
        proposal = self._proposal(record)
        if value == "accepted":
            if not proposal.output_boxes:
                return
            keep = list(
                self.output_keep.get(
                    self._record_key(record),
                    [True] * len(proposal.output_boxes),
                )
            )
            if not self.accept_materialized(record, keep):
                return
            self.records.pop(self.current)
            self.changed()
            self.current = -1
            self.selected_box = 0
            self.reload()
            return

        proposal.decision = value
        self.changed()
        next_row = min(self.current + 1, len(self.records) - 1)
        self.reload(select_record=self.records[next_row] if self.records else None)

    def retranslate(self):
        self.header_title.setText(self._tr("组合图拆分复核"))
        self.header_title.setToolTip(
            self._tr("检查原图、调整拆分框、选择保留输出并确认当前候选")
        )
        self.source_title.setText(self._tr("原图"))
        self.source_hint.setText(
            self._tr("蓝框 = 当前框 · 空白处拖拽可新建")
        )
        self.source_hint.setToolTip(
            self._tr(
                "点击左侧框或右侧输出切换当前框；当前蓝框可拖动 / 缩放；"
                "原图空白处直接拖拽可新建拆分框。"
            )
        )
        self.outputs_title.setText(self._tr("输出预览"))
        self.outputs_hint.setText(self._tr("勾选保留 · 点击选择"))
        self.outputs_hint.setToolTip(
            self._tr(
                "取消勾选后，该输出会在接受拆分时进入淘汰；"
                "点击输出卡片会选择左侧对应拆分框。"
            )
        )
        self.candidates_title.setText(self._tr("候选"))
        self.expand_hint.setText(self._tr("上拖展开"))
        self.expand_hint.setToolTip(
            self._tr("向上拖动分隔条可展开更多候选缩略图")
        )
        self.redetect_button.setText(self._tr("重新检测当前图"))
        self.reset_button.setText(self._tr("重置当前框"))
        self.delete_button.setText(self._tr("删除当前框"))
        self.accept_button.setText(self._tr("接受当前拆分"))
        self.accept_button.setToolTip(
            self._tr(
                "接受后：勾选输出进入推荐，未勾选输出进入淘汰；"
                "原图移入组合图隔离目录。"
            )
        )
        self.reject_button.setText(self._tr("拒绝拆分"))
        self.pending_button.setText(self._tr("恢复待定"))
        self.close_button.setText(self._tr("关闭"))
        if self.records:
            self.reload(
                select_record=(
                    self.records[self.current]
                    if 0 <= self.current < len(self.records)
                    else None
                )
            )

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange and hasattr(
            self, "accept_button"
        ):
            self.retranslate()
        super().changeEvent(event)

    def toggle_theme(self):
        if not self._fluent:
            return
        theme = "dark" if self._preferred_theme != "dark" else "light"
        self.apply_theme(theme)

    def apply_theme(self, theme):
        self._preferred_theme = "dark" if theme == "dark" else "light"
        dark = self._preferred_theme == "dark"
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if dark
                else self._fluent["Theme"].LIGHT
            )
        self.roi_preview.set_theme(dark)
        self._apply_candidate_state_colors()

        if dark:
            self.setStyleSheet(
                "QDialog#CompositeSplitReviewDialog {"
                "background:#171717; color:#f3f3f3; }"
                "QListWidget#CompositeCandidateList,"
                "QListWidget#CompositeOutputGrid {"
                "background:transparent; border:none; outline:none; }"
                "QListWidget#CompositeCandidateList::item {"
                "border:1px solid #3f4448; border-radius:8px;"
                "padding:5px; margin:2px; }"
                "QListWidget#CompositeCandidateList::item:selected {"
                "border:2px solid #60a5fa; color:#f3f3f3; }"
                "QListWidget#CompositeOutputGrid::item {"
                "border:1px solid #3a3a3a; border-radius:8px;"
                "padding:6px; margin:2px; background:#252525; }"
                "QListWidget#CompositeOutputGrid::item:selected {"
                "border:2px solid #60a5fa; background:#29384a; color:#f3f3f3; }"
                "QSplitter::handle { background:rgba(255,255,255,18); }"
                "QSplitter::handle:hover { background:rgba(96,165,250,105); }"
            )
        else:
            self.setStyleSheet(
                "QDialog#CompositeSplitReviewDialog {"
                "background:#f5f7fa; color:#1f2328; }"
                "QListWidget#CompositeCandidateList,"
                "QListWidget#CompositeOutputGrid {"
                "background:transparent; border:none; outline:none; }"
                "QListWidget#CompositeCandidateList::item {"
                "border:1px solid #d6dbe1; border-radius:8px;"
                "padding:5px; margin:2px; }"
                "QListWidget#CompositeCandidateList::item:selected {"
                "border:2px solid #6aa7e8; color:#1f2328; }"
                "QListWidget#CompositeOutputGrid::item {"
                "border:1px solid #dfe4ea; border-radius:8px;"
                "padding:6px; margin:2px; background:#ffffff; }"
                "QListWidget#CompositeOutputGrid::item:selected {"
                "border:2px solid #6aa7e8; background:#edf5ff; color:#1f2328; }"
                "QSplitter::handle { background:rgba(0,0,0,12); }"
                "QSplitter::handle:hover { background:rgba(0,120,212,105); }"
            )

    def closeEvent(self, event):
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if self._initial_global_dark
                else self._fluent["Theme"].LIGHT
            )
        super().closeEvent(event)
