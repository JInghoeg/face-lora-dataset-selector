"""Qt presentation for Duplicate Review.

Business queries and mutations are delegated to SelectorApplication. This file
owns only dialog state, widgets, thumbnails, and OS-level open-image behavior.

The Fluent presentation follows the human-approved v0.4 Duplicate Review
prototype. Source environments without QFluentWidgets retain the legacy Qt
fallback instead of failing application startup.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt, QSize
from PySide6.QtGui import QColor, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


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


def _human_bytes(value):
    n = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


class DuplicateGroupList(QListWidget):
    """Bottom thumbnail navigator with one row visible by default."""

    DEFAULT_HEIGHT = 108

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
        self.setMinimumHeight(106)
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
        hint.setHeight(106)
        return hint


class DuplicateCompareGrid(QListWidget):
    """Responsive duplicate-member grid; images keep their aspect ratio."""

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

        if count <= 2:
            cols = count
        elif count <= 4:
            cols = 2
        elif count <= 8:
            cols = 3
        else:
            cols = 4

        rows = max(1, (count + cols - 1) // cols)
        gutter = 10
        max_cell_w = 620 if count <= 4 else 520
        cell_w = max(
            250,
            min(max_cell_w, int((width - gutter * (cols + 1)) / cols)),
        )

        if rows == 1:
            cell_h = max(430, min(600, height - 16))
        elif rows == 2:
            cell_h = max(310, min(380, int((height - gutter * 3) / 2)))
        else:
            cell_h = max(310, min(350, int(cell_w * 0.78) + 112))

        metadata_h = 112
        image_h = max(180, cell_h - metadata_h)
        self.setIconSize(QSize(cell_w - 24, image_h))
        self.setGridSize(QSize(cell_w, cell_h))

        item_size = QSize(max(1, cell_w - 8), max(1, cell_h - 8))
        for row in range(self.count()):
            self.item(row).setSizeHint(item_size)


class DuplicateReviewDialog(QDialog):
    _preferred_theme = "light"

    def __init__(self, backend, records, on_changed, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.records = records
        self.on_changed = on_changed
        self.current_group = None
        self.draft_checks = {
            record.sample_id: (record.status == "推荐") for record in records
        }
        self.dirty = False
        self.regroup_needed = False
        self._window_drag_offset = None
        self._cleaned = False

        self._fluent = _load_fluent()
        self._initial_global_dark = (
            bool(self._fluent["isDarkTheme"]()) if self._fluent else False
        )
        if self._fluent:
            self.setWindowFlag(Qt.FramelessWindowHint, True)
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if self._preferred_theme == "dark"
                else self._fluent["Theme"].LIGHT
            )

        self.setObjectName("DuplicateReviewDialog")
        self.resize(1580, 940)

        if self._fluent:
            self._ui_fluent()
        else:
            self._ui_fallback()

        self.retranslate()
        self.apply_theme(self._preferred_theme)

    def mousePressEvent(self, event):
        if (
            self._fluent
            and event.button() == Qt.LeftButton
            and event.position().y() <= 58
        ):
            self._window_drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._fluent
            and self._window_drag_offset is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._window_drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._window_drag_offset = None
        super().mouseReleaseEvent(event)

    def _ui_fluent(self):
        api = self._fluent
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.header_title = api["StrongBodyLabel"]("")
        self.header_title.setStyleSheet("font-size:20px;")
        header.addWidget(self.header_title)
        self.header_subtitle = api["CaptionLabel"]("")
        header.addWidget(self.header_subtitle)
        header.addStretch(1)
        self.header_state = api["CaptionLabel"]("")
        header.addWidget(self.header_state)

        self.theme_button = api["TransparentToolButton"](
            api["FluentIcon"].QUIET_HOURS
        )
        self.theme_button.setFixedSize(34, 30)
        self.theme_button.setIconSize(QSize(16, 16))
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)

        self.top_close_button = api["TransparentToolButton"](
            api["FluentIcon"].CLOSE
        )
        self.top_close_button.setFixedSize(34, 30)
        self.top_close_button.clicked.connect(self.accept)
        header.addWidget(self.top_close_button)
        root.addLayout(header)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setObjectName("DuplicateMainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setOpaqueResize(True)

        self.work_card = api["SimpleCardWidget"]()
        work_layout = QVBoxLayout(self.work_card)
        work_layout.setContentsMargins(10, 10, 10, 10)
        work_layout.setSpacing(8)

        group_head = QHBoxLayout()
        self.group_label = api["StrongBodyLabel"]("")
        group_head.addWidget(self.group_label)
        self.group_status = api["CaptionLabel"]("")
        group_head.addWidget(self.group_status)
        group_head.addStretch(1)
        self.helper = api["CaptionLabel"]("")
        group_head.addWidget(self.helper)
        work_layout.addLayout(group_head)

        self.members = DuplicateCompareGrid()
        self.members.itemChanged.connect(self.member_check_changed)
        self.members.itemDoubleClicked.connect(self.open_member)
        work_layout.addWidget(self.members, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.best_button = api["PushButton"]("")
        self.all_keep_button = api["PushButton"]("")
        self.restore_button = api["PushButton"]("")
        self.restore_button.setIcon(api["FluentIcon"].SYNC)
        self.toggle_grouping = api["PushButton"]("")
        for button in (
            self.best_button,
            self.all_keep_button,
            self.restore_button,
            self.toggle_grouping,
        ):
            button.setMinimumHeight(40)
            actions.addWidget(button)
        actions.addStretch(1)

        self.selected_button = api["PrimaryPushButton"]("")
        self.selected_button.setMinimumHeight(42)
        self.selected_button.setMinimumWidth(290)
        actions.addWidget(self.selected_button)
        work_layout.addLayout(actions)

        self.best_button.clicked.connect(self.keep_best)
        self.all_keep_button.clicked.connect(self.keep_all)
        self.restore_button.clicked.connect(self.restore_auto)
        self.toggle_grouping.clicked.connect(self.toggle_ignore)
        self.selected_button.clicked.connect(self.keep_checked)

        self.main_splitter.addWidget(self.work_card)

        self.group_card = api["SimpleCardWidget"]()
        group_layout = QVBoxLayout(self.group_card)
        group_layout.setContentsMargins(8, 6, 8, 8)
        group_layout.setSpacing(4)

        nav_head = QHBoxLayout()
        nav_head.setSpacing(8)
        self.navigator_title = api["StrongBodyLabel"]("")
        nav_head.addWidget(self.navigator_title)
        self.group_counts = api["CaptionLabel"]("")
        nav_head.addWidget(self.group_counts)
        self.navigator_hint = api["CaptionLabel"]("")
        nav_head.addWidget(self.navigator_hint)
        nav_head.addStretch(1)

        self.all_groups_button = api["PushButton"]("")
        self.all_groups_button.setIcon(api["FluentIcon"].COMPLETED)
        self.all_groups_button.setMinimumHeight(34)
        self.all_groups_button.clicked.connect(self.commit_all_groups)
        nav_head.addWidget(self.all_groups_button)
        group_layout.addLayout(nav_head)

        self.group_list = DuplicateGroupList()
        self.group_list.currentItemChanged.connect(
            lambda current, _previous: self.show_group(current)
        )
        group_layout.addWidget(self.group_list)
        self.main_splitter.addWidget(self.group_card)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        root.addWidget(self.main_splitter, 1)
        QTimer.singleShot(0, self._apply_initial_group_strip_size)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_button = api["TransparentPushButton"]("")
        self.close_button.clicked.connect(self.accept)
        footer.addWidget(self.close_button)
        self.size_grip = QSizeGrip(self)
        footer.addWidget(self.size_grip)
        root.addLayout(footer)

        self.hint = None

    def _ui_fallback(self):
        root = QVBoxLayout(self)
        self.header_title = None
        self.header_subtitle = None
        self.header_state = None
        self.group_status = None
        self.helper = None
        self.navigator_title = None
        self.group_counts = None
        self.navigator_hint = None
        self.theme_button = None
        self.top_close_button = None
        self.work_card = None
        self.group_card = None
        self.main_splitter = None

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            "padding:6px;color:#333;background:#f3f4f6;"
            "border:1px solid #d1d5db;"
        )
        root.addWidget(self.hint)

        split = QSplitter(Qt.Horizontal)
        self.group_list = QListWidget()
        self.group_list.setMinimumWidth(220)
        self.group_list.itemClicked.connect(self.show_group)
        split.addWidget(self.group_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.group_label = QLabel("")
        self.group_label.setStyleSheet("font-weight:600;")
        right_layout.addWidget(self.group_label)

        self.members = QListWidget()
        self.members.setViewMode(QListWidget.IconMode)
        self.members.setResizeMode(QListWidget.Adjust)
        self.members.setMovement(QListWidget.Static)
        self.members.setIconSize(QSize(280, 280))
        self.members.setGridSize(QSize(340, 390))
        self.members.setWordWrap(True)
        self.members.itemChanged.connect(self.member_check_changed)
        self.members.itemDoubleClicked.connect(self.open_member)
        right_layout.addWidget(self.members, 1)
        split.addWidget(right)
        split.setSizes([230, 1230])
        root.addWidget(split, 1)

        actions = QHBoxLayout()
        self.best_button = QPushButton("")
        self.selected_button = QPushButton("")
        self.all_groups_button = QPushButton("")
        self.all_keep_button = QPushButton("")
        self.restore_button = QPushButton("")
        self.toggle_grouping = QPushButton("")
        self.best_button.clicked.connect(self.keep_best)
        self.selected_button.clicked.connect(self.keep_checked)
        self.all_groups_button.clicked.connect(self.commit_all_groups)
        self.all_keep_button.clicked.connect(self.keep_all)
        self.restore_button.clicked.connect(self.restore_auto)
        self.toggle_grouping.clicked.connect(self.toggle_ignore)
        for button in (
            self.best_button,
            self.selected_button,
            self.all_groups_button,
            self.all_keep_button,
            self.restore_button,
            self.toggle_grouping,
        ):
            actions.addWidget(button)
        actions.addStretch(1)

        self.close_button = QPushButton("")
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)
        self.size_grip = QSizeGrip(self)
        actions.addWidget(self.size_grip)
        root.addLayout(actions)

    def _apply_initial_group_strip_size(self):
        if self.main_splitter is None:
            return
        sizes = self.main_splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        target = 156
        self.main_splitter.setSizes([max(1, total - target), target])

    @staticmethod
    def _tr(source):
        return QCoreApplication.translate("DuplicateReviewDialog", source)

    def status_text(self, value):
        return {
            "推荐": self._tr("推荐"),
            "备选": self._tr("备选"),
            "淘汰": self._tr("淘汰"),
        }.get(value, value)

    def category_text(self, value):
        return {
            "近景/头肩": self._tr("近景/头肩"),
            "半身": self._tr("半身"),
            "大半身": self._tr("大半身"),
            "全身": self._tr("全身"),
            "正脸": self._tr("正脸"),
            "左3/4": self._tr("左3/4"),
            "右3/4": self._tr("右3/4"),
            "左侧脸": self._tr("左侧脸"),
            "右侧脸": self._tr("右侧脸"),
        }.get(value, value)

    def retranslate(self):
        self.setWindowTitle(self._tr("重复组人工复核"))
        if self.header_title is not None:
            self.header_title.setText(self._tr("重复组人工复核"))
            self.header_subtitle.setText(
                self._tr("同组多图直接比较 · 勾选保留项 · 完成本组")
            )
            self.helper.setText(
                self._tr("双击图片打开原图 · 勾选状态切组后保留")
            )
            self.navigator_title.setText(self._tr("重复组导航"))
            self.navigator_hint.setText(
                self._tr("缩略图定位 · 上拖展开更多组")
            )
        elif self.hint is not None:
            self.hint.setText(
                self._tr(
                    "勾选只是本窗口里的临时选择；切换重复组不会丢失。点击“完成本组：勾选推荐 / 未勾淘汰”后才写入人工状态。双击图片可打开原图。"
                )
            )

        self.best_button.setText(self._tr("保留组内最佳"))
        self.selected_button.setText(
            self._tr("完成本组：勾选推荐 / 未勾淘汰")
        )
        self.selected_button.setToolTip(
            self._tr("完成本组后自动切到下一未完成组")
        )
        self.all_groups_button.setText(self._tr("完成全部组"))
        self.all_keep_button.setText(self._tr("全部保留"))
        self.restore_button.setText(self._tr("恢复组内自动状态"))
        self.close_button.setText(self._tr("关闭"))
        if self.top_close_button is not None:
            self.top_close_button.setToolTip(self._tr("关闭"))
        self._update_theme_tooltip()
        self.reload_groups(self.current_group)

    def _update_theme_tooltip(self):
        if self.theme_button is None:
            return
        self.theme_button.setToolTip(
            self._tr("切换到浅色模式")
            if self._preferred_theme == "dark"
            else self._tr("切换到深色模式")
        )

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange and hasattr(self, "best_button"):
            self.retranslate()
        super().changeEvent(event)

    @staticmethod
    def thumb(path, max_w=620, max_h=520):
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            size.scale(max_w, max_h, Qt.KeepAspectRatio)
            reader.setScaledSize(size)
        image = reader.read()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def toggle_theme(self):
        if not self._fluent:
            return
        new_theme = "dark" if self._preferred_theme != "dark" else "light"
        type(self)._preferred_theme = new_theme
        self.apply_theme(new_theme)

    def apply_theme(self, theme):
        if not self._fluent:
            return
        dark = theme == "dark"
        self._fluent["setTheme"](
            self._fluent["Theme"].DARK if dark else self._fluent["Theme"].LIGHT
        )
        self.theme_button.setIcon(
            self._fluent["FluentIcon"].BRIGHTNESS
            if dark
            else self._fluent["FluentIcon"].QUIET_HOURS
        )
        self._update_theme_tooltip()

        card_color = QColor(255, 255, 255, 13 if dark else 170)
        for card in (self.work_card, self.group_card):
            if hasattr(card, "setBackgroundColor"):
                card.setBackgroundColor(card_color)
            card.update()

        if dark:
            self.setStyleSheet(
                "QDialog#DuplicateReviewDialog { background:#202020; color:#f2f2f2; }"
                "QListWidget#DuplicateGroupList, QListWidget#DuplicateCompareGrid {"
                "background:transparent; border:none; outline:none; color:#f2f2f2; }"
                "QListWidget#DuplicateGroupList::item, QListWidget#DuplicateCompareGrid::item {"
                "border:1px solid #3a3a3a; border-radius:8px; padding:5px; margin:2px;"
                "background:#252525; }"
                "QListWidget#DuplicateGroupList::item:hover, QListWidget#DuplicateCompareGrid::item:hover {"
                "border:1px solid #5f7f9f; background:#2b2b2b; }"
                "QListWidget#DuplicateGroupList::item:selected {"
                "border:2px solid #60cdff; background:rgba(96,205,255,28); color:#f2f2f2; }"
                "QListWidget#DuplicateGroupList QScrollBar:vertical, QListWidget#DuplicateCompareGrid QScrollBar:vertical {"
                "background:#202020; width:10px; border:none; }"
                "QListWidget#DuplicateGroupList QScrollBar::handle:vertical, QListWidget#DuplicateCompareGrid QScrollBar::handle:vertical {"
                "background:#686868; min-height:28px; border-radius:5px; }"
                "QSplitter#DuplicateMainSplitter::handle:vertical {"
                "background:rgba(255,255,255,22); border-radius:3px; margin:1px; }"
                "QSplitter#DuplicateMainSplitter::handle:vertical:hover {"
                "background:rgba(96,205,255,150); }"
            )
        else:
            self.setStyleSheet(
                "QDialog#DuplicateReviewDialog { background:#f5f7fa; color:#1f2328; }"
                "QListWidget#DuplicateGroupList, QListWidget#DuplicateCompareGrid {"
                "background:transparent; border:none; outline:none; color:#1f2328; }"
                "QListWidget#DuplicateGroupList::item, QListWidget#DuplicateCompareGrid::item {"
                "border:1px solid #e1e5ea; border-radius:8px; padding:5px; margin:2px;"
                "background:#ffffff; }"
                "QListWidget#DuplicateGroupList::item:hover, QListWidget#DuplicateCompareGrid::item:hover {"
                "border:1px solid #a8c7ef; background:#fbfdff; }"
                "QListWidget#DuplicateGroupList::item:selected {"
                "border:2px solid #6aa7e8; background:#e8f1ff; color:#0f6cbd; }"
                "QListWidget#DuplicateGroupList QScrollBar:vertical, QListWidget#DuplicateCompareGrid QScrollBar:vertical {"
                "background:#f3f3f3; width:10px; border:none; }"
                "QListWidget#DuplicateGroupList QScrollBar::handle:vertical, QListWidget#DuplicateCompareGrid QScrollBar::handle:vertical {"
                "background:#b7b7b7; min-height:28px; border-radius:5px; }"
                "QSplitter#DuplicateMainSplitter::handle:vertical {"
                "background:rgba(0,0,0,10); border-radius:3px; margin:1px; }"
                "QSplitter#DuplicateMainSplitter::handle:vertical:hover {"
                "background:rgba(0,120,212,110); }"
            )

    def remember_checks(self):
        for index in range(self.members.count()):
            item = self.members.item(index)
            record_index = item.data(Qt.UserRole)
            if isinstance(record_index, int) and 0 <= record_index < len(self.records):
                self.draft_checks[self.records[record_index].sample_id] = (
                    item.checkState() == Qt.Checked
                )

    def member_check_changed(self, item):
        record_index = item.data(Qt.UserRole)
        if isinstance(record_index, int) and 0 <= record_index < len(self.records):
            self.draft_checks[self.records[record_index].sample_id] = (
                item.checkState() == Qt.Checked
            )

    def open_member(self, item):
        record_index = item.data(Qt.UserRole)
        if isinstance(record_index, int) and 0 <= record_index < len(self.records):
            try:
                os.startfile(str(self.records[record_index].path))
            except OSError as exc:
                QMessageBox.warning(self, self._tr("无法打开图片"), str(exc))

    def grouped(self, group_id):
        return self.backend.duplicate_group_members(self.records, group_id)

    @staticmethod
    def _display_group_id(group_id):
        try:
            return f"{int(group_id):02d}"
        except (TypeError, ValueError):
            return str(group_id)

    def _group_item(self, group_id, members, done, ignored=False):
        if ignored:
            text = (
                self._tr("已人工移出 · {count} 张").format(count=len(members))
                + "\n"
                + self._tr("已人工移出自动重复分组")
            )
        else:
            text = (
                self._tr("组 {group_id} · {count} 张").format(
                    group_id=self._display_group_id(group_id),
                    count=len(members),
                )
                + "\n"
                + (self._tr("✓ 已完成") if done else self._tr("未完成"))
            )

        if self._fluent and members:
            icon = QIcon(self.thumb(members[0].path, 72, 58))
            item = QListWidgetItem(icon, text)
            item.setSizeHint(QSize(142, 100))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
        else:
            item = QListWidgetItem(text)
        item.setData(Qt.UserRole, group_id)
        return item

    def _update_group_counts(self):
        if self.group_counts is None:
            return
        group_ids = list(self.backend.duplicate_group_ids(self.records))
        done = sum(
            self.backend.duplicate_group_reviewed(self.records, group_id)
            for group_id in group_ids
        )
        self.group_counts.setText(
            self._tr("未完成 {pending} · 已完成 {done}").format(
                pending=len(group_ids) - done,
                done=done,
            )
        )

    def reload_groups(self, prefer=None):
        self.remember_checks()
        self.group_list.blockSignals(True)
        try:
            self.group_list.clear()

            for group_id in self.backend.duplicate_group_ids(self.records):
                members = self.grouped(group_id)
                done = self.backend.duplicate_group_reviewed(
                    self.records, group_id
                )
                self.group_list.addItem(
                    self._group_item(group_id, members, done)
                )

            ignored = self.grouped(self.backend.duplicate_ignored_group_id)
            if ignored:
                self.group_list.addItem(
                    self._group_item(
                        self.backend.duplicate_ignored_group_id,
                        ignored,
                        False,
                        ignored=True,
                    )
                )

            if not self.group_list.count():
                self.group_label.setText(self._tr("当前没有重复组"))
                self.members.clear()
                self.current_group = None
                if self.header_state is not None:
                    self.header_state.setText(self._tr("当前没有重复组"))
                self._update_group_counts()
                return

            row = 0
            if prefer is not None:
                for index in range(self.group_list.count()):
                    if self.group_list.item(index).data(Qt.UserRole) == prefer:
                        row = index
                        break

            self.group_list.setCurrentRow(row)
            item = self.group_list.item(row)
        finally:
            self.group_list.blockSignals(False)

        self._update_group_counts()
        self.show_group(item)

    def show_group(self, item):
        if item is None:
            return

        self.remember_checks()
        group_id = item.data(Qt.UserRole)
        self.current_group = group_id
        members = self.grouped(group_id)
        done = self.backend.duplicate_group_reviewed(self.records, group_id)

        self.members.blockSignals(True)
        self.members.clear()

        ignored = group_id == self.backend.duplicate_ignored_group_id
        title = (
            self._tr("已人工移出自动重复分组")
            if ignored
            else self._tr("重复组 {group_id}").format(
                group_id=self._display_group_id(group_id)
            )
        )
        status = (
            self._tr("已人工移出自动重复分组")
            if ignored
            else (self._tr("✓ 已完成") if done else self._tr("未完成"))
        )
        self.group_label.setText(
            title + self._tr(" · {count} 张").format(count=len(members))
        )
        if self.group_status is not None:
            self.group_status.setText(status)
            self.group_status.setStyleSheet(
                "color:#4c8b4c;" if done else "color:#c77700;"
            )
        if self.header_state is not None:
            if ignored:
                self.header_state.setText(
                    title
                    + self._tr(" · {count} 张").format(count=len(members))
                )
            else:
                total_groups = len(
                    list(self.backend.duplicate_group_ids(self.records))
                )
                self.header_state.setText(
                    self._tr(
                        "组 {group_id} / {total} · {count} 张 · {state}"
                    ).format(
                        group_id=self._display_group_id(group_id),
                        total=total_groups,
                        count=len(members),
                        state=status,
                    )
                )

        self.toggle_grouping.setText(
            self._tr("勾选项恢复自动分组")
            if ignored
            else self._tr("勾选项移出重复组")
        )

        if hasattr(self.members, "set_member_count"):
            self.members.set_member_count(len(members))

        for rank_no, record in enumerate(members, 1):
            record_index = next(
                index for index, value in enumerate(self.records) if value is record
            )
            prefix = "★ " if not ignored and rank_no == 1 else ""
            checked = self.draft_checks.get(
                record.sample_id, record.status == "推荐"
            )
            text = (
                f"{prefix}{record.path.name}\n"
                f"{record.width}×{record.height} · {_human_bytes(record.file_size)}\n"
                f"FIQA {record.face_quality:.3f} · BRISQUE {record.brisque:.1f}\n"
                + self._tr("清晰度 {value}").format(value=f"{record.blur:.0f}")
                + f" · {self.category_text(record.person_scale)}"
                + f" · {self.category_text(record.angle_class)}"
            )
            eligibility_text = (
                self._tr("可直接用")
                if record.eligibility == "PASS"
                else (
                    self._tr("需复核")
                    if record.eligibility == "REVIEW"
                    else self._tr("硬淘汰")
                )
            )
            max_w = 620 if self._fluent else 280
            max_h = 520 if self._fluent else 280
            list_item = QListWidgetItem(
                QIcon(self.thumb(record.path, max_w, max_h)),
                text,
            )
            list_item.setData(Qt.UserRole, record_index)
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            list_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            list_item.setToolTip(
                f"{record.sample_id}\n"
                + self._tr("文件：{size} · {width}×{height}").format(
                    size=_human_bytes(record.file_size),
                    width=record.width,
                    height=record.height,
                )
                + "\n"
                + self._tr("状态：{status} · 判定：{eligibility}").format(
                    status=self.status_text(record.status),
                    eligibility=eligibility_text,
                )
            )
            self.members.addItem(list_item)

        self.members.blockSignals(False)
        if hasattr(self.members, "reflow"):
            self.members.reflow()

    def checked_records(self):
        self.remember_checks()
        return [
            record
            for record in self.current_records()
            if self.draft_checks.get(record.sample_id, False)
        ]

    def current_records(self):
        if self.current_group is None:
            return []
        return self.grouped(self.current_group)

    def changed(self, prefer=None, regroup=False):
        self.dirty = True
        self.regroup_needed = self.regroup_needed or regroup
        self.reload_groups(prefer)

    def _cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if self._initial_global_dark
                else self._fluent["Theme"].LIGHT
            )

    def done(self, result):
        self._cleanup()
        if self.dirty:
            self.on_changed(self.regroup_needed)
        super().done(result)

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def _sync_drafts_from_current(self):
        for record in self.current_records():
            self.draft_checks[record.sample_id] = record.status == "推荐"

    def keep_best(self):
        if self.current_group in (
            None,
            self.backend.duplicate_ignored_group_id,
        ):
            return
        if self.backend.duplicate_keep_best(self.records, self.current_group):
            self._sync_drafts_from_current()
            self.changed(self.current_group)

    def _advance_to_next_unfinished(self, completed_group):
        if completed_group in (
            None,
            self.backend.duplicate_ignored_group_id,
        ):
            return False

        current_row = -1
        for row in range(self.group_list.count()):
            if self.group_list.item(row).data(Qt.UserRole) == completed_group:
                current_row = row
                break

        if current_row < 0:
            return False

        for row in range(current_row + 1, self.group_list.count()):
            item = self.group_list.item(row)
            group_id = item.data(Qt.UserRole)
            if group_id == self.backend.duplicate_ignored_group_id:
                continue
            if self.backend.duplicate_group_reviewed(self.records, group_id):
                continue

            self.group_list.setCurrentRow(row)
            self.group_list.scrollToItem(
                item,
                QAbstractItemView.PositionAtCenter,
            )
            if not self._fluent:
                self.show_group(item)
            return True
        return False

    def keep_checked(self):
        members = self.current_records()
        if not members:
            return
        completed_group = self.current_group
        selected = {record.sample_id for record in self.checked_records()}
        if self.backend.duplicate_apply_checked(
            self.records, completed_group, selected
        ):
            self.changed(completed_group)
            self._advance_to_next_unfinished(completed_group)

    def commit_all_groups(self):
        self.remember_checks()
        selected = {
            sample_id
            for sample_id, checked in self.draft_checks.items()
            if checked
        }
        if self.backend.duplicate_apply_all_groups(self.records, selected):
            self.changed(self.current_group)

    def keep_all(self):
        if self.backend.duplicate_keep_all(self.records, self.current_group):
            self._sync_drafts_from_current()
            self.changed(self.current_group)

    def restore_auto(self):
        if self.backend.duplicate_restore_auto(self.records, self.current_group):
            for record in self.current_records():
                self.draft_checks[record.sample_id] = False
            self.changed(self.current_group)

    def toggle_ignore(self):
        checked = self.checked_records()
        if not checked:
            QMessageBox.information(
                self,
                self._tr("未勾选图片"),
                self._tr("请先勾选需要调整重复分组的图片。"),
            )
            return

        restore = self.current_group == self.backend.duplicate_ignored_group_id
        changed = self.backend.duplicate_set_ignored(
            self.records,
            {record.sample_id for record in checked},
            ignored=not restore,
        )
        if changed:
            self.changed(
                self.backend.duplicate_ignored_group_id if not restore else None,
                True,
            )
