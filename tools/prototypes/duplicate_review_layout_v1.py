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
from PySide6.QtCore import Qt, QSize, QEvent
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DuplicateGroupList")
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


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
        count = self._member_count

        # The comparison task determines density:
        # 2 members -> large side-by-side;
        # 3-4 -> one comparison row when space permits;
        # 5-8 -> 3 columns, prioritizing readable images over "show all at once";
        # 9+ -> 4 columns and scroll.
        if count <= 2:
            cols = count
        elif count <= 4:
            cols = min(4, count)
        elif count <= 8:
            cols = 3
        else:
            cols = 4

        gutter = 10
        cell_w = max(250, min(520, int((width - gutter * (cols + 1)) / cols)))
        image_h = max(180, min(330, int(cell_w * 0.66)))
        cell_h = image_h + 126
        self.setIconSize(QSize(cell_w - 24, image_h))
        self.setGridSize(QSize(cell_w, cell_h))


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

        main = QSplitter(Qt.Horizontal)
        main.setObjectName("DuplicateMainSplitter")
        main.setChildrenCollapsible(False)
        main.setHandleWidth(7)

        # LEFT: navigation only. Global-scope action stays with the group list.
        left = SimpleCardWidget()
        left.setMinimumWidth(210)
        left.setMaximumWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        nav_head = QHBoxLayout()
        nav_title = StrongBodyLabel("重复组")
        nav_head.addWidget(nav_title)
        nav_head.addStretch(1)
        self.group_counts = CaptionLabel("未完成 15 · 已完成 3")
        nav_head.addWidget(self.group_counts)
        left_layout.addLayout(nav_head)

        self.group_list = GroupList()
        self.group_list.setMinimumWidth(190)
        left_layout.addWidget(self.group_list, 1)

        self.complete_all = PushButton("完成全部组")\n        self.complete_all.setIcon(FluentIcon.COMPLETED)
        self.complete_all.setMinimumHeight(40)
        self.complete_all.setToolTip("将各组当前暂存的勾选结果一次性写入")
        left_layout.addWidget(self.complete_all)
        main.addWidget(left)

        # RIGHT: one visual hierarchy. No duplicate inspector sidebar.
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
        self.restore = PushButton("恢复组内自动状态")\n        self.restore.setIcon(FluentIcon.SYNC)
        self.move_out = PushButton("勾选项移出重复组")
        for button in (self.keep_best, self.keep_all, self.restore, self.move_out):
            button.setMinimumHeight(40)
            actions.addWidget(button)

        actions.addStretch(1)

        self.finish_group = PrimaryPushButton("完成本组：勾选推荐 / 未勾淘汰")
        self.finish_group.setMinimumHeight(42)
        self.finish_group.setMinimumWidth(290)
        actions.addWidget(self.finish_group)
        work_layout.addLayout(actions)
        main.addWidget(work)

        main.setStretchFactor(0, 0)
        main.setStretchFactor(1, 1)
        main.setSizes([230, 1330])
        root.addWidget(main, 1)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self))
        root.addLayout(grip_row)

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
        for group_id, count, done in groups:
            mark = "✓" if done else "•"
            text = f"{mark}  组 {group_id:02d}  ·  {count} 张"
            item = QListWidgetItem(text)
            item.setSizeHint(QSize(196, 42))
            item.setData(Qt.UserRole, group_id)
            self.group_list.addItem(item)
        self.group_list.setCurrentRow(2)

    def _populate_members(self):
        self.members.blockSignals(True)
        self.members.clear()
        for index, record in enumerate(self.members_data, 1):
            pix = load_fitted_pixmap(record.path, self.members.iconSize())
            prefix = "★ 推荐最佳\n" if record.best else ""
            text = (
                prefix
                + f"{record.path.name}\n"
                + f"{record.width}×{record.height} · {record.size_mb:.1f} MB\n"
                + f"FIQA {record.fiqa:.3f} · BRISQUE {record.brisque:.1f} · 清晰度 {record.sharpness}\n"
                + f"{record.scale} · {record.angle}"
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
            "QListWidget#DuplicateGroupList::item { border-radius:6px; padding:6px 7px; margin:1px 0; }"
            "QListWidget#DuplicateGroupList::item:hover { background:rgba(0,0,0,0.035); }"
            "QListWidget#DuplicateGroupList::item:selected { background:#e8f1ff; color:#0f6cbd; }"
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
