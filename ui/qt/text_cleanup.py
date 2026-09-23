"""Qt presentation for the Text Cleanup feature.

Model/runtime, persistence, repair and filesystem behavior stay behind
SelectorApplication. This module owns only Qt interaction/presentation and thin
worker adapters.
"""
from __future__ import annotations

import math
import traceback
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Qt, Signal, QSize, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .image_preview import ImagePreview
from .thumbnail import ThumbnailWorker


def _path_key(path):
    return str(Path(path).resolve()).casefold()


def _combo_value(combo):
    value = combo.currentData()
    return combo.currentText() if value is None else value


def _set_combo_value(combo, value):
    index = combo.findData(value)
    if index < 0:
        index = combo.findText(value)
    if index >= 0:
        combo.setCurrentIndex(index)


class TextScan(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, backend, folder, cached):
        super().__init__()
        self.backend = backend
        self.folder = folder
        self.cached = cached

    def run(self):
        try:
            records = self.backend.scan_text_cleanup(
                self.folder,
                cached=self.cached,
                progress=self.progress.emit,
            )
            self.finished.emit(records)
        except Exception:
            self.failed.emit(traceback.format_exc())


class TextCleanupBatchWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, backend, folder, output, records, method, expand, radius):
        super().__init__()
        self.backend = backend
        self.folder = folder
        self.output = output
        self.records = list(records)
        self.method = method
        self.expand = expand
        self.radius = radius

    def run(self):
        try:
            result = self.backend.batch_text_cleanup(
                folder=self.folder,
                output=self.output,
                records=self.records,
                method=self.method,
                expand=self.expand,
                radius=self.radius,
                progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class SubtitleTab(QWidget):
    PAGE_SIZE = 80

    def __init__(self, backend, app_dir, thumbnail_cache):
        super().__init__()
        self.backend = backend
        self.app_dir = Path(app_dir)
        self.thumbnail_cache = Path(thumbnail_cache)
        self.folder = None
        self.output = None
        self.records = []
        self.current = -1
        self.thread = None
        self.worker = None
        self.page = 0
        self.visible = []
        self.thumb_memory = OrderedDict()
        self.thumb_threads = []
        self.thumb_token = 0
        self.item_by_record = {}
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.ui()
        self.restore()

    @staticmethod
    def _tr(source):
        return QCoreApplication.translate("TextCleanupTab", source)

    def _retranslate_combo(self, combo, items, default_value):
        current = _combo_value(combo) if combo.count() else default_value
        combo.blockSignals(True)
        combo.clear()
        for source, value in items:
            combo.addItem(self._tr(source), value)
        _set_combo_value(combo, current if current not in (None, "") else default_value)
        combo.blockSignals(False)

    def retranslate(self):
        self.pick_input_btn.setText(self._tr("选择输入目录"))
        self.pick_output_btn.setText(self._tr("选择输出目录"))
        if not self.folder:
            self.input.setText(self._tr("未选择输入目录"))
        if not self.output:
            self.output_label.setText(self._tr("未选择输出目录"))
        self.scan.setText(self._tr("扫描文字"))
        self.update_add_button_text()
        self.delete_btn.setText(self._tr("删除选中区域"))
        self.method_label.setText(self._tr("方式"))
        self._retranslate_combo(
            self.method,
            [
                ("AI 修复（MI-GAN）", "AI 修复（MI-GAN）"),
                ("快速修复（TELEA）", "快速修复（TELEA）"),
                ("Navier-Stokes", "Navier-Stokes"),
            ],
            "AI 修复（MI-GAN）",
        )
        self.expand.setPrefix(self._tr("Mask 扩张 "))
        self.radius.setPrefix(self._tr("修复半径 "))
        self.preview_btn.setText(self._tr("预览修复"))
        self.batch_btn.setText(self._tr("批量处理到新目录"))
        self.view_label.setText(self._tr("查看"))
        self._retranslate_combo(
            self.view,
            [
                ("全部图片", "全部图片"),
                ("仅显示需要修复", "仅显示需要修复"),
                ("仅显示有文字", "仅显示有文字"),
                ("仅显示人工修改", "仅显示人工修改"),
            ],
            "全部图片",
        )
        self.select_suggested_btn.setText(self._tr("全选建议修复"))
        self.clear_page_btn.setText(self._tr("取消当前页全部"))
        self.min_height.setPrefix(self._tr("最小高 "))
        self.min_area.setPrefix(self._tr("最小面积 "))
        self.min_conf.setPrefix(self._tr("最低置信度 "))
        self.legend.setText(self._tr("灰色＝检测到文字；绿色＝建议/已选修复；橙色＝人工修改。勾选仅控制修复。"))
        self.prev_image.setText(self._tr("上一张"))
        self.next_image.setText(self._tr("下一张"))
        self.prev_page.setText(self._tr("上一页"))
        self.next_page.setText(self._tr("下一页"))
        if self.records:
            self.refresh(False)
        else:
            self.page_label.setText(self._tr("第 0/0 页"))
            self.update_summary()

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange and hasattr(self, "pick_input_btn"):
            self.retranslate()
        super().changeEvent(event)

    def update_add_button_text(self):
        self.add.setText(self._tr("添加区域：开") if self.add.isChecked() else self._tr("添加区域：关"))

    def ui(self):
        layout = QVBoxLayout(self)
        paths = QGridLayout()
        self.input = QLabel()
        self.output_label = QLabel()
        self.pick_input_btn = QPushButton()
        self.pick_output_btn = QPushButton()
        self.pick_input_btn.clicked.connect(self.pick_input)
        self.pick_output_btn.clicked.connect(self.pick_output)
        paths.addWidget(self.pick_input_btn, 0, 0)
        paths.addWidget(self.input, 0, 1)
        paths.addWidget(self.pick_output_btn, 1, 0)
        paths.addWidget(self.output_label, 1, 1)
        layout.addLayout(paths)

        controls = QHBoxLayout()
        self.scan = QPushButton()
        self.scan.clicked.connect(self.start_scan)
        self.add = QPushButton()
        self.add.setCheckable(True)
        self.add.toggled.connect(
            lambda enabled: (
                self.preview.__setattr__("add", enabled),
                self.update_add_button_text(),
            )
        )
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(self.delete)
        self.method = QComboBox()
        self.expand = QSpinBox()
        self.expand.setRange(0, 40)
        self.expand.setValue(5)
        self.radius = QSpinBox()
        self.radius.setRange(1, 30)
        self.radius.setValue(4)
        self.preview_btn = QPushButton()
        self.preview_btn.clicked.connect(self.preview_repair)
        self.batch_btn = QPushButton()
        self.batch_btn.clicked.connect(self.start_batch)
        self.method_label = QLabel()
        for widget in (
            self.scan,
            self.add,
            self.delete_btn,
            self.method_label,
            self.method,
            self.expand,
            self.radius,
            self.preview_btn,
            self.batch_btn,
        ):
            controls.addWidget(widget)
        layout.addLayout(controls)

        filters = QHBoxLayout()
        self.view = QComboBox()
        self.view.currentIndexChanged.connect(self.filter_changed)
        self.select_suggested_btn = QPushButton()
        self.select_suggested_btn.clicked.connect(self.select_suggested)
        self.clear_page_btn = QPushButton()
        self.clear_page_btn.clicked.connect(self.clear_page)
        self.min_height = QSpinBox()
        self.min_height.setRange(2, 80)
        self.min_height.setValue(6)
        self.min_area = QSpinBox()
        self.min_area.setRange(4, 5000)
        self.min_area.setValue(36)
        self.min_conf = QDoubleSpinBox()
        self.min_conf.setRange(0, 0.99)
        self.min_conf.setSingleStep(0.05)
        self.min_conf.setValue(0.0)
        self.view_label = QLabel()
        for widget in (
            self.view_label,
            self.view,
            self.select_suggested_btn,
            self.clear_page_btn,
            self.min_height,
            self.min_area,
            self.min_conf,
        ):
            filters.addWidget(widget)
        for widget in (self.min_height, self.min_area, self.min_conf):
            widget.valueChanged.connect(self.filter_changed)
        filters.addStretch(1)
        self.summary = QLabel()
        filters.addWidget(self.summary)
        layout.addLayout(filters)
        self.bar = QProgressBar()
        layout.addWidget(self.bar)

        splitter = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setIconSize(QSize(110, 110))
        self.list.setGridSize(QSize(135, 150))
        self.list.itemClicked.connect(self.show)
        splitter.addWidget(self.list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.preview = ImagePreview()
        self.preview.drawn.connect(self.new_box)
        right_layout.addWidget(self.preview, 1)
        self.legend = QLabel()
        right_layout.addWidget(self.legend)
        self.boxes = QListWidget()
        self.boxes.itemChanged.connect(self.checked)
        right_layout.addWidget(self.boxes)
        image_nav = QHBoxLayout()
        self.prev_image = QPushButton()
        self.prev_image.clicked.connect(lambda: self.move_image(-1))
        self.next_image = QPushButton()
        self.next_image.clicked.connect(lambda: self.move_image(1))
        image_nav.addWidget(self.prev_image)
        image_nav.addWidget(self.next_image)
        right_layout.addLayout(image_nav)
        splitter.addWidget(right)
        splitter.setSizes([500, 800])
        layout.addWidget(splitter, 1)

        page_nav = QHBoxLayout()
        self.prev_page = QPushButton()
        self.prev_page.clicked.connect(lambda: self.change_page(-1))
        self.page_label = QLabel()
        self.next_page = QPushButton()
        self.next_page.clicked.connect(lambda: self.change_page(1))
        page_nav.addStretch(1)
        page_nav.addWidget(self.prev_page)
        page_nav.addWidget(self.page_label)
        page_nav.addWidget(self.next_page)
        page_nav.addStretch(1)
        layout.addLayout(page_nav)
        self.retranslate()

    def pick_input(self):
        value = QFileDialog.getExistingDirectory(
            self,
            self._tr("选择待去字幕图片目录"),
            str(self.folder or self.app_dir),
        )
        if value:
            self.folder = Path(value)
            self.input.setText(value)
            self.schedule_save()

    def pick_output(self):
        value = QFileDialog.getExistingDirectory(
            self,
            self._tr("选择输出目录（只写新文件）"),
            str(self.output or self.app_dir),
        )
        if value:
            self.output = Path(value)
            self.output_label.setText(value)
            self.schedule_save()

    def state_records(self):
        try:
            return self.backend.text_cleanup_state_records(self.folder) if self.folder else {}
        except Exception:
            return {}

    def start_scan(self):
        if not self.folder or self.thread and self.thread.isRunning():
            return
        self.scan.setEnabled(False)
        self.bar.setRange(0, 0)
        self.thread = QThread(self)
        self.worker = TextScan(self.backend, self.folder, self.state_records())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.scan_progress)
        self.worker.finished.connect(self.scanned)
        self.worker.failed.connect(
            lambda error: QMessageBox.critical(self, self._tr("扫描失败"), error)
        )
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.done)
        self.thread.start()

    def scan_progress(self, current, total, name):
        self.bar.setRange(0, total)
        self.bar.setValue(current)
        self.bar.setFormat(self._tr("扫描文字 {current}/{total}: {name}").format(current=current,total=total,name=name))

    def scanned(self, records):
        self.records = records
        self.current = -1
        self.page = 0
        self.refresh()
        self.schedule_save()
        self.bar.setFormat(self._tr("扫描完成：{count} 张").format(count=len(records)))

    def done(self):
        self.scan.setEnabled(True)
        self.worker = None
        self.thread.deleteLater()
        self.thread = None

    def eligible(self, record):
        return self.backend.text_cleanup_eligible(
            record,
            min_height=self.min_height.value(),
            min_area=self.min_area.value(),
            min_conf=self.min_conf.value(),
        )

    def current_size(self, record):
        if (
            self.current >= 0
            and self.records[self.current] is record
            and self.preview.img is not None
        ):
            record.height, record.width = self.preview.img.shape[:2]
            return record.height, record.width
        return self.backend.text_cleanup_ensure_size(record)

    def filtered(self):
        mode = _combo_value(self.view)
        output = []
        for index, record in enumerate(self.records):
            good = self.eligible(record)
            if mode == "仅显示需要修复" and not any(
                record.selected[item] for item in good
            ):
                continue
            if mode == "仅显示有文字" and not good:
                continue
            if mode == "仅显示人工修改" and not any(record.manual):
                continue
            output.append(index)
        return output

    def status_text(self, record):
        good = self.eligible(record)
        return (
            f"{record.path.name}\n"
            + self._tr("检测 {detected} · 建议 {suggested}{manual}").format(
                detected=len(good),
                suggested=sum(record.selected[index] for index in good),
                manual=self._tr(" · 人工") if any(record.manual) else "",
            )
        )

    def placeholder(self):
        pixmap = QPixmap(110, 110)
        pixmap.fill(QColor("#e8edf2"))
        return pixmap

    def refresh(self, preserve=True):
        old = self.current
        scroll = self.list.verticalScrollBar().value()
        self.visible = self.filtered()
        pages = max(1, math.ceil(len(self.visible) / self.PAGE_SIZE))
        self.page = min(self.page, pages - 1)
        shown = self.visible[
            self.page * self.PAGE_SIZE : (self.page + 1) * self.PAGE_SIZE
        ]
        self.thumb_token += 1
        token = self.thumb_token
        self.list.clear()
        self.item_by_record = {}
        for index in shown:
            item = QListWidgetItem(
                QIcon(self.placeholder()),
                self.status_text(self.records[index]),
            )
            item.setData(Qt.UserRole, index)
            self.list.addItem(item)
            self.item_by_record[index] = item
        self.page_label.setText(
            self._tr("第 {page}/{pages} 页 · 显示 {shown} / {total} 张").format(
                page=self.page + 1,
                pages=pages,
                shown=len(shown),
                total=len(self.visible),
            )
        )
        self.prev_page.setEnabled(self.page > 0)
        self.next_page.setEnabled(self.page + 1 < pages)
        self.update_summary()
        self.start_thumbnails(token, shown)
        if preserve and old in self.item_by_record:
            self.list.setCurrentItem(self.item_by_record[old])
            QTimer.singleShot(
                0,
                lambda: self.list.verticalScrollBar().setValue(scroll),
            )

    def filter_changed(self, *_):
        self.page = 0
        self.refresh(False)

    def change_page(self, delta):
        self.page = max(0, self.page + delta)
        self.refresh(False)

    def start_thumbnails(self, token, indices):
        missing = []
        for index in indices:
            value = self.thumb_memory.get(_path_key(self.records[index].path))
            if value is not None:
                self.thumb_memory.move_to_end(_path_key(self.records[index].path))
                self.thumbnail_ready(token, index, value)
            else:
                missing.append((index, self.records[index]))
        if not missing:
            return
        thread = QThread(self)
        worker = ThumbnailWorker(token, missing, self.thumbnail_cache)
        thread._subtitle_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(self.thumbnail_ready)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda current=thread: self.thumb_done(current))
        self.thumb_threads.append(thread)
        thread.start()

    def thumb_done(self, thread):
        if thread in self.thumb_threads:
            self.thumb_threads.remove(thread)
        thread.deleteLater()

    def thumbnail_ready(self, token, index, image):
        cache_key = _path_key(self.records[index].path)
        self.thumb_memory[cache_key] = image
        self.thumb_memory.move_to_end(cache_key)
        while len(self.thumb_memory) > 600:
            self.thumb_memory.popitem(last=False)
        if token == self.thumb_token and index in self.item_by_record:
            self.item_by_record[index].setIcon(QIcon(QPixmap.fromImage(image)))

    def show(self, item):
        self.current = item.data(Qt.UserRole)
        record = self.records[self.current]
        image = self.backend.text_cleanup_load_image(record.path)
        self.preview.set_data(
            image,
            record.boxes,
            record.selected,
            record.manual,
        )
        self.refresh_boxes()

    def move_image(self, delta):
        if not self.visible:
            return
        try:
            position = self.visible.index(self.current)
        except ValueError:
            position = -1
        index = self.visible[max(0, min(len(self.visible) - 1, position + delta))]
        if index not in self.item_by_record:
            self.page = self.visible.index(index) // self.PAGE_SIZE
            self.refresh(False)
        self.list.setCurrentItem(self.item_by_record[index])
        self.show(self.item_by_record[index])

    def refresh_boxes(self):
        self.boxes.blockSignals(True)
        self.boxes.clear()
        if self.current >= 0:
            record = self.records[self.current]
            for index, box in enumerate(record.boxes):
                points = np.asarray(box)
                state = (
                    self._tr("建议修复")
                    if index < len(record.suggested) and record.suggested[index]
                    else self._tr("检测到文字")
                )
                state += self._tr("（人工）") if record.manual[index] else ""
                item = QListWidgetItem(
                    self._tr("{state} · 区域 {index}: ").format(
                        state=state,
                        index=index + 1,
                    )
                    f"{points[:, 0].min()},{points[:, 1].min()} - "
                    f"{points[:, 0].max()},{points[:, 1].max()}"
                )
                item.setData(Qt.UserRole, index)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Checked if record.selected[index] else Qt.Unchecked
                )
                self.boxes.addItem(item)
        self.boxes.blockSignals(False)

    def update_item(self, index):
        if index in self.item_by_record:
            self.item_by_record[index].setText(
                self.status_text(self.records[index])
            )

    def checked(self, item):
        if self.current < 0:
            return
        record = self.records[self.current]
        index = item.data(Qt.UserRole)
        record.selected[index] = item.checkState() == Qt.Checked
        record.manual[index] = True
        self.preview.set_data(
            self.preview.img,
            record.boxes,
            record.selected,
            record.manual,
        )
        self.update_item(self.current)
        self.update_summary()
        self.schedule_save()

    def new_box(self, box):
        if self.current < 0:
            return
        record = self.records[self.current]
        record.boxes.append(box)
        record.suggested.append(False)
        record.selected.append(True)
        record.manual.append(True)
        record.scores.append(1.0)
        self.preview.set_data(
            self.preview.img,
            record.boxes,
            record.selected,
            record.manual,
        )
        self.refresh_boxes()
        self.update_item(self.current)
        self.update_summary()
        self.schedule_save()

    def delete(self):
        if self.current < 0:
            return
        record = self.records[self.current]
        for index in sorted(
            (item.data(Qt.UserRole) for item in self.boxes.selectedItems()),
            reverse=True,
        ):
            for values in (
                record.boxes,
                record.selected,
                record.manual,
                record.scores,
                record.suggested,
            ):
                del values[index]
        self.preview.set_data(
            self.preview.img,
            record.boxes,
            record.selected,
            record.manual,
        )
        self.refresh_boxes()
        self.update_item(self.current)
        self.update_summary()
        self.schedule_save()

    def select_suggested(self):
        for index in self.visible[
            self.page * self.PAGE_SIZE : (self.page + 1) * self.PAGE_SIZE
        ]:
            record = self.records[index]
            for box_index, suggested in enumerate(record.suggested):
                if suggested:
                    record.selected[box_index] = True
                    record.manual[box_index] = True
            self.update_item(index)
        if self.current >= 0:
            record = self.records[self.current]
            self.preview.set_data(
                self.preview.img,
                record.boxes,
                record.selected,
                record.manual,
            )
            self.refresh_boxes()
        self.update_summary()
        self.schedule_save()

    def clear_page(self):
        for index in self.visible[
            self.page * self.PAGE_SIZE : (self.page + 1) * self.PAGE_SIZE
        ]:
            record = self.records[index]
            record.selected = [False] * len(record.selected)
            record.manual = [True] * len(record.manual)
            self.update_item(index)
        if self.current >= 0:
            record = self.records[self.current]
            self.preview.set_data(
                self.preview.img,
                record.boxes,
                record.selected,
                record.manual,
            )
            self.refresh_boxes()
        self.update_summary()
        self.schedule_save()

    def update_summary(self):
        detected = sum(len(self.eligible(record)) for record in self.records)
        selected = sum(
            sum(record.selected[index] for index in self.eligible(record))
            for record in self.records
        )
        manual = sum(any(record.manual) for record in self.records)
        self.summary.setText(
            self._tr("检测到文字：{detected} · 建议修复：{selected} · 人工修改：{manual}").format(
                detected=detected, selected=selected, manual=manual
            )
        )

    def preview_repair(self):
        if self.current < 0:
            return
        try:
            if (
                _combo_value(self.method) == "AI 修复（MI-GAN）"
                and not self.backend.text_cleanup_migan_ready()
            ):
                QMessageBox.information(
                    self,
                    self._tr("首次使用 MI-GAN"),
                    self._tr("首次使用会自动从上游下载约 28 MB 的 MI-GAN 模型。下载完成后会自动校验文件。"),
                )
            image = self.backend.text_cleanup_repair(
                self.records[self.current],
                method=_combo_value(self.method),
                expand=self.expand.value(),
                radius=self.radius.value(),
            )
            self.preview.set_data(image, [], [], [])
        except Exception as exc:
            QMessageBox.critical(self, self._tr("预览修复失败"), str(exc))

    def start_batch(self):
        if not self.folder or not self.output or not self.records:
            QMessageBox.information(
                self,
                self._tr("缺少内容"),
                self._tr("请先选择输入、输出目录并扫描文字。"),
            )
            return
        if self.thread and self.thread.isRunning():
            return
        if (
            self.output.resolve() == self.folder.resolve()
            or self.folder.resolve() in self.output.resolve().parents
        ):
            QMessageBox.warning(
                self,
                self._tr("输出目录无效"),
                self._tr("输出目录必须是源目录以外的新目录。"),
            )
            return
        self.scan.setEnabled(False)
        self.bar.setRange(0, len(self.records))
        self.bar.setValue(0)
        self.bar.setFormat(self._tr("批量处理准备中…"))
        self.thread = QThread(self)
        self.worker = TextCleanupBatchWorker(
            self.backend,
            self.folder,
            self.output,
            self.records,
            _combo_value(self.method),
            self.expand.value(),
            self.radius.value(),
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.batch_progress)
        self.worker.finished.connect(self.batch_done)
        self.worker.failed.connect(self.batch_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.done)
        self.thread.start()

    def batch_progress(self, current, total, name):
        self.bar.setRange(0, total)
        self.bar.setValue(current)
        self.bar.setFormat(self._tr("批量处理 {current}/{total}: {name}").format(current=current,total=total,name=name))

    def batch_done(self, result):
        self.bar.setFormat(self._tr("批量处理完成：{count} 张").format(count=result.written))
        QMessageBox.information(
            self,
            self._tr("批量处理完成"),
            self._tr("已写入 {count} 张图片到新目录：\n{output}\n\n源图片未被修改。").format(count=result.written,output=self.output),
        )

    def batch_failed(self, error):
        self.bar.setFormat(self._tr("批量处理失败"))
        QMessageBox.critical(self, self._tr("批量处理失败"), error)

    def restore(self):
        try:
            state = self.backend.text_cleanup_load_state()
            self.folder = state.folder
            self.output = state.output
            self.input.setText(
                str(self.folder) if self.folder else self._tr("未选择输入目录")
            )
            self.output_label.setText(
                str(self.output) if self.output else self._tr("未选择输出目录")
            )
            _set_combo_value(self.method, state.method)
            self.expand.setValue(state.expand)
            self.radius.setValue(state.radius)
            self.min_height.setValue(state.min_height)
            self.min_area.setValue(state.min_area)
            self.min_conf.setValue(state.min_conf)
            self.records = list(state.records)
            if self.records:
                self.refresh(False)
        except Exception:
            pass

    def schedule_save(self):
        self.save_timer.start(450)

    def save(self):
        try:
            self.backend.text_cleanup_save_state(
                folder=self.folder,
                output=self.output,
                records=self.records,
                method=_combo_value(self.method),
                expand=self.expand.value(),
                radius=self.radius.value(),
                min_height=self.min_height.value(),
                min_area=self.min_area.value(),
                min_conf=self.min_conf.value(),
            )
        except Exception:
            pass
