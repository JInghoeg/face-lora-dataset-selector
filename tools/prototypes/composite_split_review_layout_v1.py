"""Visual-only Composite Split Review prototype for v0.4.

This prototype is isolated from production code. It renders a concrete
Qt/QFluentWidgets candidate for human review before any production replacement.

Design goals:
- source image + editable split boxes are the primary visual task;
- suggested outputs are large enough to judge, not tiny thumbnails;
- candidate navigation follows the accepted bottom one-row / expand-up pattern;
- local decisions have one clear primary action;
- accepted / pending / rejected candidates are scannable by background state;
- production manual ROI should reuse the proven Auto Crop ROI interaction.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtCore import QPointF, QRectF, Qt, QSize, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
    setTheme,
)


@dataclass
class DemoCandidate:
    candidate_id: int
    path: Path
    boxes: list[tuple[int, int, int, int]]
    mode: str
    decision: str = "pending"


class SourceBoxPreview(QWidget):
    """Image preview with all proposal boxes and one visibly editable box."""

    boxSelected = Signal(int)

    BOX_COLORS = ("#5dade2", "#58d68d", "#af7ac5", "#f5b041")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CompositeSourcePreview")
        self.setMinimumSize(520, 430)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = QPixmap()
        self._source_size = QSize()
        self._boxes: list[tuple[int, int, int, int]] = []
        self._selected = 0
        self._display_rect = QRectF()

    def set_data(self, path: Path, boxes, selected=0):
        self._pixmap = QPixmap(str(path))
        self._source_size = self._pixmap.size()
        self._boxes = list(boxes)
        self._selected = max(0, min(selected, len(self._boxes) - 1)) if self._boxes else -1
        self.update()

    def set_selected(self, index: int):
        if 0 <= index < len(self._boxes):
            self._selected = index
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#111418"))

        if self._pixmap.isNull() or self._source_size.isEmpty():
            painter.end()
            return

        fitted = self._pixmap.scaled(
            self.size() - QSize(24, 24),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = (self.width() - fitted.width()) / 2
        y = (self.height() - fitted.height()) / 2
        self._display_rect = QRectF(x, y, fitted.width(), fitted.height())
        painter.drawPixmap(int(x), int(y), fitted)

        sx = fitted.width() / self._source_size.width()
        sy = fitted.height() / self._source_size.height()

        for index, box in enumerate(self._boxes):
            x0, y0, x1, y1 = box
            rect = QRectF(
                x + x0 * sx,
                y + y0 * sy,
                max(1, (x1 - x0) * sx),
                max(1, (y1 - y0) * sy),
            )
            color = QColor(self.BOX_COLORS[index % len(self.BOX_COLORS)])
            selected = index == self._selected

            pen = QPen(QColor("#60cdff") if selected else color)
            pen.setWidth(3 if selected else 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 5, 5)

            badge = QRectF(rect.left() + 7, rect.top() + 7, 28, 24)
            painter.fillRect(badge, QColor("#60cdff") if selected else color)
            painter.setPen(QColor("#101418"))
            painter.drawText(badge, Qt.AlignCenter, str(index + 1))

            if selected:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#ffffff"))
                handles = [
                    QPointF(rect.left(), rect.top()),
                    QPointF(rect.center().x(), rect.top()),
                    QPointF(rect.right(), rect.top()),
                    QPointF(rect.right(), rect.center().y()),
                    QPointF(rect.right(), rect.bottom()),
                    QPointF(rect.center().x(), rect.bottom()),
                    QPointF(rect.left(), rect.bottom()),
                    QPointF(rect.left(), rect.center().y()),
                ]
                for point in handles:
                    painter.drawRect(
                        QRectF(point.x() - 4, point.y() - 4, 8, 8)
                    )
                painter.setBrush(Qt.NoBrush)
        painter.end()

    def mousePressEvent(self, event):
        if not self._display_rect.isValid() or self._source_size.isEmpty():
            return super().mousePressEvent(event)
        p = event.position()
        if not self._display_rect.contains(p):
            return super().mousePressEvent(event)

        sx = self._source_size.width() / self._display_rect.width()
        sy = self._source_size.height() / self._display_rect.height()
        source_x = (p.x() - self._display_rect.left()) * sx
        source_y = (p.y() - self._display_rect.top()) * sy

        for index, (x0, y0, x1, y1) in enumerate(self._boxes):
            if x0 <= source_x <= x1 and y0 <= source_y <= y1:
                self._selected = index
                self.boxSelected.emit(index)
                self.update()
                break
        super().mousePressEvent(event)


class OutputGrid(QListWidget):
    """Large suggested-output cards; two columns at normal dialog width."""

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


class CandidateList(QListWidget):
    """Bottom candidate navigator: one row by default, expand upward on drag."""

    DEFAULT_HEIGHT = 108

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
        self.setMinimumHeight(106)
        self.setMaximumHeight(106)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(self.DEFAULT_HEIGHT)
        return hint


class CompositeSplitPrototype(QDialog):
    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.candidates = build_candidates(root)
        self.current = 2
        self.selected_output = 0
        self.output_keep: dict[int, list[bool]] = {}

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setObjectName("CompositeSplitPrototype")
        self.resize(1580, 940)
        setTheme(Theme.LIGHT)

        self._build()
        self._populate_candidates()
        self._show_candidate(self.current)
        self._apply_style()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = StrongBodyLabel("组合图拆分复核")
        title.setStyleSheet("font-size:20px;")
        header.addWidget(title)
        header.addWidget(
            CaptionLabel("检查原图 · 调整拆分框 · 选择保留输出 · 确认当前候选")
        )
        header.addStretch(1)
        self.header_state = CaptionLabel("")
        header.addWidget(self.header_state)

        self.theme_button = TransparentToolButton(FluentIcon.QUIET_HOURS)
        self.theme_button.setFixedSize(34, 30)
        header.addWidget(self.theme_button)

        self.top_close = TransparentToolButton(FluentIcon.CLOSE)
        self.top_close.setFixedSize(34, 30)
        self.top_close.clicked.connect(self.reject)
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

        work = QSplitter(Qt.Horizontal)
        work.setObjectName("CompositeWorkSplitter")
        work.setChildrenCollapsible(False)
        work.setHandleWidth(8)

        # Source / editable proposal side.
        self.source_card = SimpleCardWidget()
        source_layout = QVBoxLayout(self.source_card)
        source_layout.setContentsMargins(10, 10, 10, 10)
        source_layout.setSpacing(7)

        source_head = QHBoxLayout()
        self.source_title = StrongBodyLabel("原图与拆分框")
        source_head.addWidget(self.source_title)
        self.mode_label = CaptionLabel("")
        source_head.addWidget(self.mode_label)
        source_head.addStretch(1)
        self.add_box = PushButton("+ 添加拆分框")
        self.add_box.setMinimumHeight(34)
        self.add_box.clicked.connect(self._add_manual_box)
        self.add_box.hide()
        source_head.addWidget(self.add_box)

        self.reset_box = TransparentPushButton("重置当前框")
        self.reset_box.setIcon(FluentIcon.SYNC)
        source_head.addWidget(self.reset_box)
        source_layout.addLayout(source_head)

        self.source_hint = CaptionLabel(
            "点击其他框切换编辑 · 当前蓝框可拖动，并可从四边 / 四角缩放"
        )
        source_layout.addWidget(self.source_hint)

        self.source_preview = SourceBoxPreview()
        self.source_preview.boxSelected.connect(self._select_output)
        source_layout.addWidget(self.source_preview, 1)

        self.source_meta = CaptionLabel("")
        source_layout.addWidget(self.source_meta)
        work.addWidget(self.source_card)

        # Suggested outputs side.
        self.outputs_card = SimpleCardWidget()
        outputs_layout = QVBoxLayout(self.outputs_card)
        outputs_layout.setContentsMargins(10, 10, 10, 10)
        outputs_layout.setSpacing(7)

        outputs_head = QHBoxLayout()
        outputs_head.addWidget(StrongBodyLabel("建议输出"))
        self.output_count = CaptionLabel("")
        outputs_head.addWidget(self.output_count)
        outputs_head.addStretch(1)
        outputs_layout.addLayout(outputs_head)

        outputs_layout.addWidget(
            CaptionLabel("取消勾选 = 接受拆分后该输出直接进入淘汰；点击输出可定位对应拆分框")
        )

        self.outputs = OutputGrid()
        self.outputs.currentRowChanged.connect(self._select_output)
        self.outputs.itemChanged.connect(self._output_check_changed)
        outputs_layout.addWidget(self.outputs, 1)
        work.addWidget(self.outputs_card)

        work.setStretchFactor(0, 3)
        work.setStretchFactor(1, 2)
        work.setSizes([900, 600])
        self.main_splitter.addWidget(work)

        # Bottom navigator + action row.
        self.nav_card = SimpleCardWidget()
        nav_layout = QVBoxLayout(self.nav_card)
        nav_layout.setContentsMargins(8, 6, 8, 8)
        nav_layout.setSpacing(4)

        nav_head = QHBoxLayout()
        nav_head.setSpacing(8)
        nav_head.addWidget(StrongBodyLabel("组合图候选"))
        self.nav_counts = CaptionLabel("")
        nav_head.addWidget(self.nav_counts)
        nav_head.addWidget(CaptionLabel("缩略图定位 · 上拖展开更多候选"))
        nav_head.addStretch(1)
        nav_layout.addLayout(nav_head)

        self.candidate_list = CandidateList()
        self.candidate_list.currentRowChanged.connect(self._show_candidate)
        nav_layout.addWidget(self.candidate_list)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.accept_button = PrimaryPushButton("接受当前拆分")
        self.accept_button.setMinimumHeight(42)
        self.accept_button.setMinimumWidth(160)
        actions.addWidget(self.accept_button)

        self.reject_button = PushButton("拒绝拆分")
        self.reject_button.setMinimumHeight(40)
        actions.addWidget(self.reject_button)

        self.pending_button = TransparentPushButton("恢复待定")
        self.pending_button.setMinimumHeight(40)
        actions.addWidget(self.pending_button)

        self.accept_note = CaptionLabel(
            "接受后：勾选输出→推荐，未勾选→淘汰；原图移入组合图隔离目录"
        )
        actions.addWidget(self.accept_note)
        actions.addStretch(1)

        self.close_button = TransparentPushButton("关闭")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        actions.addWidget(QSizeGrip(self))
        nav_layout.addLayout(actions)

        self.main_splitter.addWidget(self.nav_card)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        root.addWidget(self.main_splitter, 1)

        QTimer.singleShot(0, self._apply_initial_nav_size)

    def _apply_initial_nav_size(self):
        sizes = self.main_splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        target = 208
        self.main_splitter.setSizes([max(1, total - target), target])
        self._default_nav_pane_height = self.main_splitter.sizes()[1]
        self.candidate_list.setMaximumHeight(106)
        self.candidate_list.updateGeometry()

    def _sync_candidate_expansion(self):
        sizes = self.main_splitter.sizes()
        if len(sizes) < 2:
            return
        default_height = getattr(self, "_default_nav_pane_height", sizes[1])
        expanded = sizes[1] > default_height + 8
        self.candidate_list.setMaximumHeight(16777215 if expanded else 106)
        self.candidate_list.updateGeometry()

    def _populate_candidates(self):
        self.candidate_list.blockSignals(True)
        for candidate in self.candidates:
            thumb = QPixmap(str(candidate.path)).scaled(
                self.candidate_list.iconSize(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            item = QListWidgetItem(QIcon(thumb), "")
            item.setData(Qt.UserRole, candidate.candidate_id)
            item.setData(Qt.UserRole + 1, candidate.decision)
            item.setSizeHint(QSize(142, 100))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self._refresh_candidate_item(item, candidate)
            self.candidate_list.addItem(item)
        self.candidate_list.blockSignals(False)
        self.candidate_list.setCurrentRow(self.current)
        self._update_nav_counts()
        self._apply_candidate_state_colors()

    def _refresh_candidate_item(self, item, candidate):
        mode = "拆分" if candidate.mode == "split_people" else "群组裁剪"
        state = {
            "accepted": "✓ 已接受",
            "rejected": "× 已拒绝",
            "pending": "• 待定",
        }[candidate.decision]
        item.setText(
            f"候选 {candidate.candidate_id:02d} · {mode} {len(candidate.boxes)}\n{state}"
        )
        item.setToolTip(
            f"候选 {candidate.candidate_id:02d} · {mode} · "
            f"{len(candidate.boxes)} 个输出 · {state}"
        )

    def _update_nav_counts(self):
        accepted = sum(c.decision == "accepted" for c in self.candidates)
        rejected = sum(c.decision == "rejected" for c in self.candidates)
        pending = len(self.candidates) - accepted - rejected
        self.nav_counts.setText(
            f"待定 {pending} · 已接受 {accepted} · 已拒绝 {rejected}"
        )

    def _apply_candidate_state_colors(self):
        palette = {
            "accepted": QColor("#dcefe2"),
            "pending": QColor("#ffe8bd"),
            "rejected": QColor("#efd6d8"),
        }
        for row in range(self.candidate_list.count()):
            item = self.candidate_list.item(row)
            decision = item.data(Qt.UserRole + 1)
            item.setData(Qt.BackgroundRole, palette.get(decision, palette["pending"]))

    def _show_candidate(self, row):
        if row < 0 or row >= len(self.candidates):
            return
        self.current = row
        candidate = self.candidates[row]
        self.selected_output = 0
        self.source_preview.set_data(candidate.path, candidate.boxes, 0)

        zero_boxes = not candidate.boxes
        self.add_box.setVisible(zero_boxes)
        self.reset_box.setVisible(not zero_boxes)
        self.accept_button.setEnabled(not zero_boxes)

        mode_long = (
            "拆成独立人物 / 视角"
            if candidate.mode == "split_people"
            else "重叠多人合并裁剪"
        )
        if zero_boxes:
            self.mode_label.setText("手动触发 · 自动分析未找到可用拆分框")
            self.source_meta.setText(
                f"{candidate.path.name} · 1600 × 1000 · 可手动添加第一个拆分框"
            )
        else:
            self.mode_label.setText(f"{mode_long} · {len(candidate.boxes)} 个输出")
            self.source_meta.setText(
                f"{candidate.path.name} · 1600 × 1000 · 当前框 1 / {len(candidate.boxes)}"
            )
        state_text = {
            "accepted": "已接受",
            "rejected": "已拒绝",
            "pending": "待定",
        }[candidate.decision]
        self.header_state.setText(
            f"候选 {candidate.candidate_id:02d} / {len(self.candidates)}"
            f" · {len(candidate.boxes)} 个输出 · {state_text}"
        )

        keep = self.output_keep.get(candidate.candidate_id)
        if keep is None or len(keep) != len(candidate.boxes):
            keep = [True] * len(candidate.boxes)
            if len(keep) >= 3:
                keep[-1] = False
            self.output_keep[candidate.candidate_id] = keep

        source = QPixmap(str(candidate.path))
        self.outputs.blockSignals(True)
        self.outputs.clear()
        for index, box in enumerate(candidate.boxes):
            x0, y0, x1, y1 = box
            crop = source.copy(x0, y0, x1 - x0, y1 - y0)
            target = self.outputs.iconSize()
            crop = crop.scaled(
                target,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            state = "推荐" if keep[index] else "淘汰"
            item = QListWidgetItem(
                QIcon(crop),
                f"输出 {index + 1}\n{x1 - x0} × {y1 - y0}\n→ {state}",
            )
            item.setData(Qt.UserRole, index)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if keep[index] else Qt.Unchecked)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.outputs.addItem(item)
        self.outputs.blockSignals(False)
        self.outputs.reflow()
        if self.outputs.count():
            self.outputs.setCurrentRow(0)
            self._update_output_count()
        else:
            self.output_count.setText("暂无输出 · 添加拆分框后实时生成预览")

    def _add_manual_box(self):
        candidate = self.candidates[self.current]
        if candidate.boxes:
            return
        # Recovery default: create one conservative centered ROI. Production
        # will hand this box to the same bounded ROI editor used by Auto Crop.
        candidate.boxes = [(360, 150, 1240, 940)]
        self.output_keep[candidate.candidate_id] = [True]
        self._show_candidate(self.current)

    def _select_output(self, index):
        if index < 0:
            return
        candidate = self.candidates[self.current]
        if index >= len(candidate.boxes):
            return
        self.selected_output = index
        self.source_preview.set_selected(index)
        self.source_meta.setText(
            f"{candidate.path.name} · 1600 × 1000"
            f" · 当前框 {index + 1} / {len(candidate.boxes)}"
        )
        if self.outputs.currentRow() != index:
            self.outputs.blockSignals(True)
            self.outputs.setCurrentRow(index)
            self.outputs.blockSignals(False)

    def _output_check_changed(self, item):
        candidate = self.candidates[self.current]
        index = item.data(Qt.UserRole)
        keep = self.output_keep[candidate.candidate_id]
        if not isinstance(index, int) or not (0 <= index < len(keep)):
            return
        keep[index] = item.checkState() == Qt.Checked
        state = "推荐" if keep[index] else "淘汰"
        lines = item.text().splitlines()
        if lines:
            lines[-1] = f"→ {state}"
            item.setText("\n".join(lines))
        self._update_output_count()

    def _update_output_count(self):
        candidate = self.candidates[self.current]
        keep = self.output_keep.get(candidate.candidate_id, [])
        self.output_count.setText(
            f"勾选 {sum(keep)} / {len(keep)} · 当前编辑输出 {self.selected_output + 1}"
        )

    def _apply_style(self):
        self.setStyleSheet(
            "QDialog#CompositeSplitPrototype { background:#f5f7fa; color:#1f2328; }"
            "QWidget#CompositeSourcePreview { border:1px solid #2b3036; border-radius:8px; }"
            "QListWidget#CompositeOutputGrid, QListWidget#CompositeCandidateList {"
            "background:transparent; border:none; outline:none; }"
            "QListWidget#CompositeOutputGrid::item {"
            "border:1px solid #dfe4ea; border-radius:8px; padding:6px; margin:2px;"
            "background:#ffffff; }"
            "QListWidget#CompositeOutputGrid::item:selected {"
            "border:2px solid #6aa7e8; background:#edf5ff; color:#0f6cbd; }"
            "QListWidget#CompositeCandidateList::item {"
            "border:1px solid #d6dbe1; border-radius:8px; padding:5px; margin:2px; }"
            "QListWidget#CompositeCandidateList::item:hover {"
            "border:1px solid #8bb8e8; }"
            "QListWidget#CompositeCandidateList::item:selected {"
            "border:2px solid #6aa7e8; background:#e8f1ff; color:#0f6cbd; }"
            "QSplitter#CompositeMainSplitter::handle:vertical,"
            "QSplitter#CompositeWorkSplitter::handle:horizontal {"
            "background:rgba(0,0,0,12); border-radius:3px; margin:1px; }"
            "QSplitter#CompositeMainSplitter::handle:vertical:hover,"
            "QSplitter#CompositeWorkSplitter::handle:horizontal:hover {"
            "background:rgba(0,120,212,105); }"
        )



class ManualEntryContextPrototype(QDialog):
    """Visualizes only the existing main-view right inspector placement.

    The broad Dataset View redesign remains paused. This mock deliberately uses
    the current native-QWidget grammar to answer one question only: where the
    selected-image recovery action belongs.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("当前图片工具位置预览")
        self.resize(620, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("主 Dataset View · 当前图片右侧区域")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        root.addWidget(title)

        stats = QGroupBox("统计（点击分类筛选）")
        stats_layout = QVBoxLayout(stats)
        stats_layout.addWidget(QLabel("推荐 126 · 备选 43 · 淘汰 18"))
        root.addWidget(stats)

        analysis = QGroupBox("图片分析数据")
        analysis_layout = QVBoxLayout(analysis)
        detail = QLabel(
            "IMG_0241.png\n"
            "1600 × 1000 · 推荐 · PASS\n"
            "FIQA 0.712 · BRISQUE 29.6 · 清晰度 94\n"
            "检测到 3 个独立人物，但自动 Composite Scan 未生成候选"
        )
        detail.setWordWrap(True)
        analysis_layout.addWidget(detail)

        tool_row = QHBoxLayout()
        self.manual_composite = QPushButton("手动组合图拆分…")
        self.manual_composite.setToolTip(
            "仅对当前选中图片重新运行组合图拆分分析；不会重扫整个数据集"
        )
        tool_row.addWidget(self.manual_composite)
        tool_row.addStretch(1)
        analysis_layout.addLayout(tool_row)
        root.addWidget(analysis)

        manual = QGroupBox("人工状态（优先于自动结果）")
        manual_layout = QGridLayout(manual)
        for column, label in enumerate(("推荐", "备选", "淘汰")):
            manual_layout.addWidget(QPushButton(label), 0, column)
        manual_layout.addWidget(QPushButton("恢复自动"), 1, 0, 1, 3)
        root.addWidget(manual)

        ai = QGroupBox("AI 审核建议")
        ai_layout = QVBoxLayout(ai)
        ai_layout.addWidget(QLabel("当前图片没有 AI 建议"))
        root.addWidget(ai)
        root.addStretch(1)

        hint = QLabel(
            "入口只属于“当前选中图片”的上下文，不放到顶部全局工具栏，"
            "避免误解为重新扫描整个数据集。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "padding:8px;color:#475569;background:#eef3f8;"
            "border:1px solid #cbd5e1;border-radius:4px;"
        )
        root.addWidget(hint)


def make_composite_image(path: Path, seed: int, people=3):
    width, height = 1600, 1000
    image = Image.new(
        "RGB",
        (width, height),
        (225 - seed * 2, 224 - seed, 218 + seed),
    )
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 690, width, height), fill=(177, 186, 178))
    draw.rectangle((0, 0, width, 160), fill=(204, 214, 220))

    centers = [(310, 470), (800, 455), (1260, 480), (1040, 470)]
    body_colors = [(90, 127, 165), (166, 102, 111), (96, 150, 116), (133, 109, 165)]
    for index in range(people):
        cx, cy = centers[index]
        head = 72
        draw.ellipse(
            (cx - head, cy - 220 - head, cx + head, cy - 220 + head),
            fill=(239, 207 - index * 5, 186),
        )
        draw.rounded_rectangle(
            (cx - 105, cy - 140, cx + 105, cy + 245),
            radius=55,
            fill=body_colors[index],
        )
        draw.rectangle(
            (cx - 80, cy + 230, cx - 18, cy + 430),
            fill=(73, 76, 84),
        )
        draw.rectangle(
            (cx + 18, cy + 230, cx + 80, cy + 430),
            fill=(73, 76, 84),
        )
    image.save(path)


def build_candidates(root: Path):
    specs = [
        ("accepted", "split_people", [(120, 170, 500, 930), (600, 160, 1000, 925)]),
        ("rejected", "group_crop", [(190, 150, 1380, 930)]),
        ("pending", "split_people", [(120, 160, 520, 940), (590, 150, 1010, 930), (1080, 165, 1470, 940)]),
        ("pending", "split_people", [(180, 170, 650, 930), (820, 160, 1380, 935)]),
        ("accepted", "group_crop", [(220, 160, 1390, 930)]),
        ("pending", "split_people", [(150, 170, 520, 925), (610, 150, 1010, 930), (1100, 180, 1450, 920)]),
        ("pending", "split_people", [(120, 175, 570, 935), (760, 165, 1400, 930)]),
        ("pending", "group_crop", [(250, 150, 1350, 920)]),
        ("rejected", "split_people", [(140, 180, 540, 930), (650, 160, 1060, 930), (1110, 170, 1460, 930)]),
        ("pending", "split_people", [(180, 150, 650, 930), (800, 160, 1390, 935)]),
        ("pending", "split_people", [(120, 165, 520, 930), (590, 150, 1010, 930), (1080, 170, 1470, 930)]),
        ("accepted", "group_crop", [(210, 160, 1370, 930)]),
    ]
    rows = []
    for idx, (decision, mode, boxes) in enumerate(specs, 1):
        path = root / f"composite_{idx:02d}.png"
        make_composite_image(path, idx, people=max(2, min(3, len(boxes))))
        rows.append(
            DemoCandidate(
                candidate_id=idx,
                path=path,
                boxes=boxes,
                mode=mode,
                decision=decision,
            )
        )
    return rows


def render(out_dir: Path):
    with tempfile.TemporaryDirectory() as td:
        dialog = CompositeSplitPrototype(Path(td))
        app = QApplication.instance()
        dialog.show()
        for _ in range(8):
            app.processEvents()
        dialog.outputs.reflow()
        app.processEvents()

        assert dialog.candidate_list.maximumHeight() == 106
        assert (
            dialog.candidate_list.viewport().height()
            <= dialog.candidate_list.gridSize().height() + 2
        )
        assert dialog.accept_button.x() < dialog.reject_button.x()
        assert dialog.outputs.count() == 3

        accepted_bg = dialog.candidate_list.item(0).data(Qt.BackgroundRole)
        rejected_bg = dialog.candidate_list.item(1).data(Qt.BackgroundRole)
        pending_bg = dialog.candidate_list.item(3).data(Qt.BackgroundRole)
        assert len({accepted_bg.name(), rejected_bg.name(), pending_bg.name()}) == 3

        compact_sizes = dialog.main_splitter.sizes()
        dialog.main_splitter.setSizes(
            [max(1, compact_sizes[0] - 180), compact_sizes[1] + 180]
        )
        dialog._sync_candidate_expansion()
        for _ in range(3):
            app.processEvents()
        assert dialog.candidate_list.maximumHeight() > 1000
        assert (
            dialog.candidate_list.viewport().height()
            > dialog.candidate_list.gridSize().height() + 2
        )
        dialog.main_splitter.setSizes(compact_sizes)
        dialog._sync_candidate_expansion()
        for _ in range(3):
            app.processEvents()

        path = out_dir / "composite_split_review_layout_v1.png"
        assert dialog.grab().save(str(path)), path
        dialog.close()
        app.processEvents()
        return path



def render_zero_detection_recovery(out_dir: Path):
    with tempfile.TemporaryDirectory() as td:
        dialog = CompositeSplitPrototype(Path(td))
        app = QApplication.instance()
        dialog.candidates[2].boxes = []
        dialog.candidate_list.setCurrentRow(2)
        dialog._show_candidate(2)
        dialog.show()
        for _ in range(8):
            app.processEvents()

        assert dialog.add_box.isVisible()
        assert not dialog.reset_box.isVisible()
        assert dialog.outputs.count() == 0
        assert not dialog.accept_button.isEnabled()

        path = out_dir / "composite_split_zero_detection_recovery_v1.png"
        assert dialog.grab().save(str(path)), path

        # The recovery action must create a usable first ROI in-place rather
        # than opening a second editor/window.
        dialog._add_manual_box()
        for _ in range(3):
            app.processEvents()
        assert dialog.outputs.count() == 1
        assert dialog.accept_button.isEnabled()
        assert not dialog.add_box.isVisible()
        assert dialog.reset_box.isVisible()

        dialog.close()
        app.processEvents()
        return path


def render_manual_entry_context(out_dir: Path):
    dialog = ManualEntryContextPrototype()
    app = QApplication.instance()
    dialog.show()
    for _ in range(5):
        app.processEvents()
    assert dialog.manual_composite.isVisible()
    path = out_dir / "composite_manual_entry_context_v1.png"
    assert dialog.grab().save(str(path)), path
    dialog.close()
    app.processEvents()
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])

    font_path = os.environ.get("COMPOSITE_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    print(render(args.out))
    print(render_zero_detection_recovery(args.out))
    print(render_manual_entry_context(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
