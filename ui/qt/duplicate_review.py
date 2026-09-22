"""Qt presentation for Duplicate Review.

Business queries and mutations are delegated to SelectorApplication. This file
owns only dialog state, widgets, thumbnails, and OS-level open-image behavior.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


def _human_bytes(value):
    n = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


class DuplicateReviewDialog(QDialog):
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

        self.setWindowTitle("Duplicate Group 人工复核")
        self.resize(1500, 900)

        root = QVBoxLayout(self)
        hint = QLabel(
            "勾选只是本窗口里的临时选择；切换 Group 不会丢失。"
            "点击“完成本组：勾选推荐 / 未勾淘汰”后才写入人工状态。"
            "双击图片可打开原图。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "padding:6px;color:#333;background:#f3f4f6;"
            "border:1px solid #d1d5db;"
        )
        root.addWidget(hint)

        split = QSplitter(Qt.Horizontal)
        self.group_list = QListWidget()
        self.group_list.setMinimumWidth(220)
        self.group_list.itemClicked.connect(self.show_group)
        split.addWidget(self.group_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.group_label = QLabel("选择左侧重复组")
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
        best = QPushButton("保留组内最佳")
        best.clicked.connect(self.keep_best)
        selected = QPushButton("完成本组：勾选推荐 / 未勾淘汰")
        selected.clicked.connect(self.keep_checked)
        all_groups = QPushButton("完成全部组")
        all_groups.clicked.connect(self.commit_all_groups)
        all_keep = QPushButton("全部保留")
        all_keep.clicked.connect(self.keep_all)
        restore = QPushButton("恢复组内自动状态")
        restore.clicked.connect(self.restore_auto)
        self.toggle_grouping = QPushButton("勾选项移出重复组")
        self.toggle_grouping.clicked.connect(self.toggle_ignore)

        for button in (
            best,
            selected,
            all_groups,
            all_keep,
            restore,
            self.toggle_grouping,
        ):
            actions.addWidget(button)
        actions.addStretch(1)

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        root.addLayout(actions)

        self.reload_groups()

    @staticmethod
    def thumb(path):
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            size.scale(280, 280, Qt.KeepAspectRatio)
            reader.setScaledSize(size)
        image = reader.read()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

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
                QMessageBox.warning(self, "无法打开图片", str(exc))

    def grouped(self, group_id):
        return self.backend.duplicate_group_members(self.records, group_id)

    def reload_groups(self, prefer=None):
        self.remember_checks()
        self.group_list.clear()

        for group_id in self.backend.duplicate_group_ids(self.records):
            members = self.grouped(group_id)
            done = self.backend.duplicate_group_reviewed(self.records, group_id)
            item = QListWidgetItem(
                f'{"✓ " if done else ""}Group {group_id} · {len(members)} 张'
            )
            item.setData(Qt.UserRole, group_id)
            self.group_list.addItem(item)

        ignored = self.grouped(self.backend.duplicate_ignored_group_id)
        if ignored:
            item = QListWidgetItem(f"已人工移出 · {len(ignored)} 张")
            item.setData(Qt.UserRole, self.backend.duplicate_ignored_group_id)
            self.group_list.addItem(item)

        if not self.group_list.count():
            self.group_label.setText("当前没有 Duplicate Group")
            self.members.clear()
            self.current_group = None
            return

        row = 0
        if prefer is not None:
            for index in range(self.group_list.count()):
                if self.group_list.item(index).data(Qt.UserRole) == prefer:
                    row = index
                    break

        self.group_list.setCurrentRow(row)
        self.show_group(self.group_list.item(row))

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
        title = "已人工移出自动重复分组" if ignored else f"Duplicate Group {group_id}"
        self.group_label.setText(
            title
            + f" · {len(members)} 张"
            + (" · ✓ 已完成" if done else " · 未完成")
        )
        self.toggle_grouping.setText(
            "勾选项恢复自动分组" if ignored else "勾选项移出重复组"
        )

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
                f"{_human_bytes(record.file_size)} · {record.width}×{record.height}\n"
                f"FIQA {record.face_quality:.3f} · BRISQUE {record.brisque:.1f} · "
                f"Sharp {record.blur:.0f}\n"
                f"{record.person_scale} · {record.angle_class}"
            )
            eligibility_text = (
                "可直接用"
                if record.eligibility == "PASS"
                else ("需复核" if record.eligibility == "REVIEW" else "硬淘汰")
            )
            list_item = QListWidgetItem(QIcon(self.thumb(record.path)), text)
            list_item.setData(Qt.UserRole, record_index)
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            list_item.setToolTip(
                f"{record.sample_id}\n"
                f"文件：{_human_bytes(record.file_size)} · "
                f"{record.width}×{record.height}\n"
                f"状态：{record.status} · 判定：{eligibility_text}"
            )
            self.members.addItem(list_item)

        self.members.blockSignals(False)

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

    def done(self, result):
        if self.dirty:
            self.on_changed(self.regroup_needed)
        super().done(result)

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

    def keep_checked(self):
        members = self.current_records()
        if not members:
            return
        selected = {record.sample_id for record in self.checked_records()}
        if self.backend.duplicate_apply_checked(
            self.records, self.current_group, selected
        ):
            self.changed(self.current_group)

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
                "未勾选图片",
                "请先勾选需要调整重复分组的图片。",
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
