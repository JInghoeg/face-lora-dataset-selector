"""Visual-only Duplicate Review layout prototype for v0.4.

This file is intentionally isolated from production code. It exists only to
render real Qt/QFluentWidgets screenshots for human visual review before any
production UI rewrite is attempted.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, QSize, QEvent, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
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
    TransparentToolButton,
    setTheme,
)


@dataclass
class DemoMember:
    path: Path
    width: int
    height: int
    size_mb: float
    fiqa: float
    brisque: float
    sharpness: int
    scale: str
    angle: str
    checked: bool = False
    best: bool = False


class GroupList(QListWidget):
    """Bottom visual group navigator: thumbnail grid + vertical scrolling."""

    DEFAULT_HEIGHT = 228

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DuplicateGroupList")
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setIconSize(QSize(72, 58))
        self.setGridSize(QSize(148, 104))
        self.setSpacing(4)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setMinimumHeight(116)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(self.DEFAULT_HEIGHT)
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setHeight(116)
        return hint


class CompareGrid(QListWidget):
    """Wrapping comparison area. Images always fit without crop/stretch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DuplicateCompareGrid")
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWordWrap(True)
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self._member_count = 1

    def set_member_count(self, count):
        self._member_count = max(1, int(count))
        self.reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self):
        width = max(1, self.viewport().width())
        height = max(1, self.viewport().height())
        count = self._member_count

        # Density follows the comparison task rather than a fixed thumbnail size.
        # Small groups should use the available review canvas; large groups keep
        # readable cards and scroll instead of shrinking into a contact sheet.
        if count <= 2:
            cols = count
        elif count <= 4:
            # Four-way duplicate review is easier to judge as a 2×2 compare
            # than as a shallow contact-sheet row.
            cols = 2
        elif count <= 8:
            cols = 3
        else:
            cols = 4

        rows = max(1, (count + cols - 1) // cols)
        gutter = 10
        max_cell_w = 620 if count <= 4 else 520
        cell_w = max(250, min(max_cell_w, int((width - gutter * (cols + 1)) / cols)))

        if rows == 1:
            # A single comparison row should occupy the canvas instead of
            # leaving a large dead zone below four-member groups.
            cell_h = max(430, min(600, height - 16))
        elif rows == 2:
            # Two rows should fit comfortably in the normal review viewport.
            cell_h = max(310, min(380, int((height - gutter * 3) / 2)))
        else:
            # 9+ members deliberately scroll; do not sacrifice readability.
            cell_h = max(310, min(350, int(cell_w * 0.78) + 112))

        metadata_h = 112
        image_h = max(180, cell_h - metadata_h)
        self.setIconSize(QSize(cell_w - 24, image_h))
        self.setGridSize(QSize(cell_w, cell_h))

        # QListView IconMode otherwise lets portrait images shrink the visual
        # item width to their natural pixmap width. Force every comparison card
        # to use the designed cell so metadata never collapses into ellipsis.
        item_size = QSize(max(1, cell_w - 8), max(1, cell_h - 8))
        for row in range(self.count()):
            self.item(row).setSizeHint(item_size)


class DuplicateReviewPrototype(QDialog):
    def __init__(self, root: Path, member_count: int = 6):
        super().__init__()
        self.root = root
        self.member_count = member_count
        self.members_data = build_members(root, member_count)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setObjectName("DuplicateReviewPrototype")
        self.resize(1580, 940)
        setTheme(Theme.LIGHT)

        self._build()
        self._populate_groups()
        self._populate_members()
        self._apply_style()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = StrongBodyLabel("重复组复核")
        title.setStyleSheet("font-size:20px;")
        header.addWidget(title)

        subtitle = CaptionLabel("同组多图直接比较 · 勾选保留项 · 完成本组")
        header.addWidget(subtitle)
        header.addStretch(1)

        self.header_state = CaptionLabel(f"组 03 / 18 · {self.member_count} 张 · 未完成")
        header.addWidget(self.header_state)

        self.theme_btn = TransparentToolButton(FluentIcon.QUIET_HOURS)
        self.theme_btn.setFixedSize(34, 30)
        header.addWidget(self.theme_btn)

        self.close_btn = TransparentToolButton(FluentIcon.CLOSE)
        self.close_btn.setFixedSize(34, 30)
        self.close_btn.clicked.connect(self.reject)
        header.addWidget(self.close_btn)
        root.addLayout(header)

        # Match the accepted Auto Crop structure: the review canvas gets the
        # full width, while navigation lives in a bottom Filmstrip that can be
        # expanded upward with a vertical splitter when more groups are needed.
        main = QSplitter(Qt.Vertical)
        main.setObjectName("DuplicateMainSplitter")
        main.setChildrenCollapsible(False)
        main.setHandleWidth(8)
        main.setOpaqueResize(True)

        work = SimpleCardWidget()
        work_layout = QVBoxLayout(work)
        work_layout.setContentsMargins(10, 10, 10, 10)
        work_layout.setSpacing(8)

        group_head = QHBoxLayout()
        self.group_title = StrongBodyLabel(f"重复组 03 · {self.member_count} 张")
        group_head.addWidget(self.group_title)
        self.group_status = CaptionLabel("● 未完成")
        self.group_status.setStyleSheet("color:#c77700;")
        group_head.addWidget(self.group_status)
        group_head.addStretch(1)
        self.helper = CaptionLabel("双击图片打开原图 · 勾选状态切组后保留")
        group_head.addWidget(self.helper)
        work_layout.addLayout(group_head)

        self.members = CompareGrid()
        self.members.set_member_count(self.member_count)
        self.members.itemDoubleClicked.connect(lambda _item: None)
        work_layout.addWidget(self.members, 1)

        # Bottom is strictly current-group scope.
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.keep_best = PushButton("★ 保留组内最佳")
        self.keep_all = PushButton("全部保留")
        self.restore = PushButton("恢复组内自动状态")
        self.restore.setIcon(FluentIcon.SYNC)
        self.move_out = PushButton("勾选项移出重复组")
        for button in (self.keep_best, self.keep_all, self.restore, self.move_out):
            button.setMinimumHeight(40)
            actions.addWidget(button)

        actions.addStretch(1)

        self.finish_group = PrimaryPushButton("完成本组：勾选推荐 / 未勾淘汰")
        self.finish_group.setMinimumHeight(42)
        self.finish_group.setMinimumWidth(290)
        self.finish_group.setToolTip("保存本组结果后自动切换到下一未完成组")
        self.finish_group.clicked.connect(self._finish_current_group_and_advance)
        actions.addWidget(self.finish_group)
        work_layout.addLayout(actions)
        main.addWidget(work)

        # Bottom group Filmstrip. Global-scope action stays with global
        # navigation, while current-group actions remain in the work card.
        group_card = SimpleCardWidget()
        group_layout = QVBoxLayout(group_card)
        group_layout.setContentsMargins(8, 6, 8, 8)
        group_layout.setSpacing(4)

        group_head = QHBoxLayout()
        group_head.setSpacing(8)
        group_title = StrongBodyLabel("重复组导航")
        group_head.addWidget(group_title)
        self.group_counts = CaptionLabel("未完成 15 · 已完成 3")
        group_head.addWidget(self.group_counts)
        group_hint = CaptionLabel("缩略图定位 · 组多时纵向滚动")
        group_head.addWidget(group_hint)
        group_head.addStretch(1)

        self.complete_all = PushButton("完成全部组")
        self.complete_all.setIcon(FluentIcon.COMPLETED)
        self.complete_all.setMinimumHeight(34)
        self.complete_all.setToolTip("将各组当前暂存的勾选结果一次性写入")
        group_head.addWidget(self.complete_all)
        group_layout.addLayout(group_head)

        self.group_list = GroupList()
        self.group_list.currentRowChanged.connect(self._show_group_row)
        group_layout.addWidget(self.group_list)
        main.addWidget(group_card)

        main.setStretchFactor(0, 1)
        main.setStretchFactor(1, 0)
        root.addWidget(main, 1)
        QTimer.singleShot(0, self._apply_initial_group_strip_size)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self))
        root.addLayout(grip_row)

    def _apply_initial_group_strip_size(self):
        sizes = self.findChild(QSplitter, "DuplicateMainSplitter").sizes()
        total = sum(sizes)
        if total <= 0:
            return
        target = 272
        self.findChild(QSplitter, "DuplicateMainSplitter").setSizes(
            [max(1, total - target), target]
        )

    def _populate_groups(self):
        groups = [
            (1, 3, True),
            (2, 5, True),
            (3, self.member_count, False),
            (4, 3, False),
            (5, 6, False),
            (6, 4, False),
            (7, 2, False),
            (8, 5, False),
            (9, 3, False),
            (10, 4, False),
            (11, 3, False),
            (12, 5, False),
            (13, 4, False),
            (14, 2, False),
            (15, 6, False),
            (16, 4, False),
            (17, 3, False),
            (18, 5, False),
        ]
        self.group_list.blockSignals(True)
        for group_id, count, done in groups:
            thumb_path = self.root / f"group_{group_id:02d}.png"
            make_demo_image(thumb_path, (360, 240), group_id % 10)
            pix = load_fitted_pixmap(thumb_path, self.group_list.iconSize())
            item = QListWidgetItem(QIcon(pix), "")
            item.setSizeHint(QSize(142, 100))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setData(Qt.UserRole, group_id)
            item.setData(Qt.UserRole + 1, count)
            item.setData(Qt.UserRole + 2, done)
            self._refresh_group_item(item)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        self.group_list.setCurrentRow(2)
        self._update_group_counts()

    @staticmethod
    def _refresh_group_item(item):
        group_id = int(item.data(Qt.UserRole))
        count = int(item.data(Qt.UserRole + 1))
        done = bool(item.data(Qt.UserRole + 2))
        state = "✓ 已完成" if done else "• 未完成"
        item.setText(f"组 {group_id:02d} · {count} 张\n{state}")
        item.setToolTip(f"重复组 {group_id:02d} · {count} 张 · {'已完成' if done else '未完成'}")

    def _update_group_counts(self):
        done = sum(
            1
            for row in range(self.group_list.count())
            if bool(self.group_list.item(row).data(Qt.UserRole + 2))
        )
        total = self.group_list.count()
        self.group_counts.setText(f"未完成 {total - done} · 已完成 {done}")

    def _show_group_row(self, row):
        if row < 0 or row >= self.group_list.count():
            return
        item = self.group_list.item(row)
        group_id = int(item.data(Qt.UserRole))
        count = int(item.data(Qt.UserRole + 1))
        done = bool(item.data(Qt.UserRole + 2))
        self.member_count = count
        self.members_data = build_members(self.root, count)
        self._populate_members()
        self.group_title.setText(f"重复组 {group_id:02d} · {count} 张")
        self.header_state.setText(
            f"组 {group_id:02d} / {self.group_list.count()} · {count} 张 · "
            + ("已完成" if done else "未完成")
        )
        self.group_status.setText("✓ 已完成" if done else "● 未完成")
        self.group_status.setStyleSheet(
            "color:#4c8b4c;" if done else "color:#c77700;"
        )

    def _finish_current_group_and_advance(self):
        row = self.group_list.currentRow()
        if row < 0:
            return
        current = self.group_list.item(row)
        current.setData(Qt.UserRole + 2, True)
        self._refresh_group_item(current)
        self._update_group_counts()

        # Workflow rule: after committing this group, move forward to the next
        # unfinished group. Never wrap back to earlier groups automatically.
        next_row = None
        for candidate in range(row + 1, self.group_list.count()):
            if not bool(self.group_list.item(candidate).data(Qt.UserRole + 2)):
                next_row = candidate
                break
        if next_row is not None:
            self.group_list.setCurrentRow(next_row)
            self.group_list.scrollToItem(
                self.group_list.item(next_row),
                QAbstractItemView.PositionAtCenter,
            )
        else:
            self._show_group_row(row)

    def _populate_members(self):
        self.members.blockSignals(True)
        self.members.clear()
        for index, record in enumerate(self.members_data, 1):
            pix = load_fitted_pixmap(record.path, self.members.iconSize())
            prefix = "★ 推荐最佳 · " if record.best else ""
            text = (
                prefix
                + f"{record.path.name}\n"
                + f"{record.width}×{record.height} · {record.size_mb:.1f} MB\n"
                + f"FIQA {record.fiqa:.3f} · BRISQUE {record.brisque:.1f}\n"
                + f"清晰度 {record.sharpness} · {record.scale} · {record.angle}"
            )
            item = QListWidgetItem(QIcon(pix), text)
            item.setFlags(
                item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsEnabled
            )
            item.setCheckState(Qt.Checked if record.checked else Qt.Unchecked)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setToolTip(
                f"{record.path.name}\n"
                f"{record.width}×{record.height} · {record.size_mb:.1f} MB\n"
                f"FIQA {record.fiqa:.3f}\n"
                f"BRISQUE {record.brisque:.1f}\n"
                f"清晰度 {record.sharpness}\n"
                f"{record.scale} · {record.angle}"
            )
            self.members.addItem(item)
        self.members.blockSignals(False)
        self.members.set_member_count(len(self.members_data))

    def _apply_style(self):
        self.setStyleSheet(
            "QDialog#DuplicateReviewPrototype { background:#f5f7fa; color:#1f2328; }"
            "QListWidget#DuplicateGroupList { background:transparent; border:none; outline:none; }"
            "QListWidget#DuplicateGroupList::item { border:1px solid #e1e5ea; border-radius:8px; padding:5px; margin:2px; background:#ffffff; }"
            "QListWidget#DuplicateGroupList::item:hover { border:1px solid #a8c7ef; background:#fbfdff; }"
            "QListWidget#DuplicateGroupList::item:selected { border:2px solid #6aa7e8; background:#e8f1ff; color:#0f6cbd; }"
            "QListWidget#DuplicateCompareGrid { background:transparent; border:none; outline:none; }"
            "QListWidget#DuplicateCompareGrid::item { border:1px solid #e1e5ea; border-radius:8px; padding:7px; background:#ffffff; }"
            "QListWidget#DuplicateCompareGrid::item:hover { border:1px solid #a8c7ef; background:#fbfdff; }"
            "QListWidget#DuplicateCompareGrid QScrollBar:vertical { width:10px; background:transparent; }"
            "QListWidget#DuplicateCompareGrid QScrollBar::handle:vertical { background:#b8bec7; min-height:28px; border-radius:5px; }"
            "QListWidget#DuplicateCompareGrid QScrollBar::add-line:vertical, "
            "QListWidget#DuplicateCompareGrid QScrollBar::sub-line:vertical { height:0px; }"
            "QSplitter#DuplicateMainSplitter::handle:horizontal { background:rgba(0,0,0,0.04); }"
        )


def load_fitted_pixmap(path: Path, target: QSize) -> QPixmap:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid():
        size.scale(target, Qt.KeepAspectRatio)
        reader.setScaledSize(size)
    image = reader.read()
    if image.isNull():
        return QPixmap()
    return QPixmap.fromImage(image)


def make_demo_image(path: Path, size: tuple[int, int], seed: int):
    w, h = size
    base = (232 - seed * 5, 221 - seed * 3, 205 + seed * 3)
    image = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(image)

    # Large visual forms make aspect-ratio handling obvious in the screenshot.
    margin = max(20, int(min(w, h) * 0.08))
    draw.rounded_rectangle(
        (margin, margin, w - margin, h - margin),
        radius=max(18, margin // 2),
        fill=(195 - seed * 3, 168 + seed * 2, 150 + seed * 4),
    )
    cx, cy = w // 2, int(h * 0.40)
    radius = max(30, int(min(w, h) * 0.18))
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(244, 216 - seed * 2, 198 - seed),
    )
    body_w = max(80, int(w * 0.34))
    draw.rounded_rectangle(
        (cx - body_w // 2, cy + radius // 2, cx + body_w // 2, h - margin),
        radius=max(16, margin // 3),
        fill=(100 + seed * 5, 121 + seed * 2, 145 + seed * 3),
    )
    image.save(path)


def build_members(root: Path, count: int):
    shapes = [
        (720, 1080),
        (1280, 720),
        (900, 900),
        (720, 1080),
        (1200, 800),
        (800, 1200),
        (1280, 720),
        (900, 1200),
        (1400, 780),
        (800, 800),
    ]
    scales = ["近景/头肩", "半身", "大半身", "近景/头肩", "半身", "全身", "半身", "近景/头肩", "大半身", "半身"]
    angles = ["正脸", "左3/4", "右3/4", "左侧脸", "右3/4", "正脸", "右侧脸", "左3/4", "正脸", "右3/4"]
    rows = []
    for i in range(count):
        w, h = shapes[i % len(shapes)]
        path = root / f"IMG_{241 + i:04d}.png"
        make_demo_image(path, (w, h), i)
        rows.append(
            DemoMember(
                path=path,
                width=w,
                height=h,
                size_mb=1.8 + (i % 5) * 0.2,
                fiqa=0.72 - i * 0.014,
                brisque=28 + i * 1.6,
                sharpness=96 - i * 2,
                scale=scales[i % len(scales)],
                angle=angles[i % len(angles)],
                checked=i in (0, 2),
                best=i == 0,
            )
        )
    return rows


def render_case(out_dir: Path, count: int):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        dialog = DuplicateReviewPrototype(root, count)
        dialog.show()
        app = QApplication.instance()
        for _ in range(6):
            app.processEvents()
        dialog.members.reflow()
        app.processEvents()
        path = out_dir / f"duplicate_review_layout_v1_{count}_mixed.png"
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

    font_path = os.environ.get("DUPLICATE_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    outputs = [
        render_case(args.out, 4),
        render_case(args.out, 6),
        render_case(args.out, 10),
    ]
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
