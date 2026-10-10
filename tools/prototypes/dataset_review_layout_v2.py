"""Visual-only v0.4 Dataset Review layout v2.

This prototype deliberately does NOT revive rejected PR #84.  It rethinks the
main Dataset Review around one primary gallery and one contextual inspector:
- compact command/query bars instead of stacked GroupBoxes;
- selected-image preview at the top of the inspector;
- Overview / Analysis / Review tabs instead of a tall card stack;
- persistent manual-state actions at the bottom of the inspector;
- low-frequency saved-view / AI-bundle / extreme actions collapsed behind More.

Production src/ is intentionally untouched.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from qfluentwidgets import (
        CaptionLabel,
        FluentIcon,
        PrimaryPushButton,
        PushButton,
        SimpleCardWidget,
        StrongBodyLabel,
        TransparentPushButton,
        TransparentToolButton,
    )
except ImportError as exc:
    raise SystemExit(f"QFluentWidgets is required for this prototype: {exc}")


STATE_COLORS = {
    "推荐": ("#dcefe2", "#2f6f44"),
    "备选": ("#fff0cc", "#8a5d00"),
    "淘汰": ("#efd6d8", "#8c2f39"),
}


def chip(text: str, bg: str, fg: str) -> QLabel:
    label = CaptionLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        f"background:{bg}; color:{fg}; border-radius:10px;"
        "padding:3px 9px; font-weight:600;"
    )
    return label


def make_thumb(index: int, size=(240, 180)) -> QPixmap:
    w, h = size
    pix = QPixmap(w, h)
    base = QColor.fromHsv((index * 31) % 360, 55, 232)
    pix.fill(base)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(238, 214 - (index % 5) * 5, 196))
    p.setPen(Qt.NoPen)
    cx = int(w * (0.46 + (index % 3 - 1) * 0.04))
    p.drawEllipse(cx - 34, 28, 68, 68)
    p.setBrush(QColor.fromHsv((index * 47 + 130) % 360, 85, 175))
    p.drawRoundedRect(cx - 55, 96, 110, 100, 32, 32)
    p.setPen(QPen(QColor(255, 255, 255, 150), 3))
    p.drawLine(18, h - 18, w - 18, h - 18)
    p.end()
    return pix


class GalleryList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("DatasetGalleryPrototype")
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QListView.SingleSelection)
        self.setSpacing(8)
        self.setIconSize(QSize(180, 135))
        self.setGridSize(QSize(206, 190))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._sync_target_styles()
        self._sync_tab_styles()
        self._sync_manual_styles()

        self.setStyleSheet(
            "QListWidget#DatasetGalleryPrototype {"
            "background:transparent; border:none; outline:none;}"
            "QListWidget#DatasetGalleryPrototype::item {"
            "background:#ffffff; border:1px solid #dce2e8; border-radius:10px;"
            "padding:6px; margin:2px; color:#1f2328;}"
            "QListWidget#DatasetGalleryPrototype::item:selected {"
            "background:#edf5ff; border:2px solid #6aa7e8; color:#1f2328;}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(320, self.viewport().width())
        cols = max(3, min(6, width // 210))
        cell_w = max(182, int((width - (cols - 1) * 8) / cols))
        icon_w = cell_w - 24
        icon_h = int(icon_w * 0.72)
        self.setIconSize(QSize(icon_w, icon_h))
        self.setGridSize(QSize(cell_w, icon_h + 54))


class DatasetReviewLayoutV2(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("DatasetReviewLayoutV2")
        self.resize(1640, 980)
        self.setMinimumSize(1180, 720)
        self._build()
        self._populate()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # One compact command surface: dataset context + workflow actions.
        command = SimpleCardWidget()
        command.setObjectName("DatasetCommandBar")
        command_grid = QGridLayout(command)
        command_grid.setContentsMargins(12, 9, 12, 9)
        command_grid.setHorizontalSpacing(8)
        command_grid.setVerticalSpacing(6)

        self.title = StrongBodyLabel("LoRA 数据集筛选")
        self.title.setStyleSheet("font-size:19px;font-weight:700;")
        command_grid.addWidget(self.title, 0, 0)

        self.folder = CaptionLabel("G:\\ComfyUI-aki\\数据集\\Danielle_v2   ·   175 张")
        self.folder.setStyleSheet("color:#66707a;")
        command_grid.addWidget(self.folder, 0, 1, 1, 4)

        self.choose = PushButton("选择文件夹")
        self.refresh = TransparentPushButton("刷新")
        command_grid.addWidget(self.choose, 0, 5)
        command_grid.addWidget(self.refresh, 0, 6)

        self.progress = CaptionLabel("分析完成 · 缓存最新")
        self.progress.setStyleSheet("color:#4f7d5f;")
        command_grid.addWidget(self.progress, 0, 7)

        self.language = QComboBox()
        self.language.addItems(["简体中文", "English"])
        self.language.setMaximumWidth(120)
        command_grid.addWidget(self.language, 0, 8)

        command_grid.addWidget(CaptionLabel("推荐目标"), 1, 0)
        self.target_group = QButtonGroup(self)
        target_wrap = QWidget()
        target_row = QHBoxLayout(target_wrap)
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.setSpacing(4)
        for value in ("60", "100", "150", "自定义"):
            b = PushButton(value)
            b.setCheckable(True)
            b.setMinimumWidth(54)
            if value == "150":
                b.setChecked(True)
            self.target_group.addButton(b)
            target_row.addWidget(b)
        self.custom_spin = QSpinBox()
        self.custom_spin.setRange(1, 3000)
        self.custom_spin.setValue(175)
        self.custom_spin.setMaximumWidth(72)
        target_row.addWidget(self.custom_spin)
        self.target_group.idClicked.connect(lambda _id: self._sync_target_styles())
        command_grid.addWidget(target_wrap, 1, 1, 1, 2)

        self.face_boxes = QCheckBox("显示人脸框")
        command_grid.addWidget(self.face_boxes, 1, 3)

        # Workflow modules are clearly separate from per-image actions.
        workflow = QWidget()
        wf = QHBoxLayout(workflow)
        wf.setContentsMargins(0, 0, 0, 0)
        wf.setSpacing(6)
        self.duplicate = PushButton("重复组复核")
        self.composite = PushButton("组合图拆分")
        self.autocrop = PushButton("自动裁剪")
        self.organizer = TransparentPushButton("整理源文件")
        for b in (self.duplicate, self.composite, self.autocrop, self.organizer):
            wf.addWidget(b)
        command_grid.addWidget(workflow, 1, 4, 1, 4)

        self.export = PrimaryPushButton("导出推荐图片")
        command_grid.addWidget(self.export, 1, 8)
        root.addWidget(command)

        # Query bar: frequently changed view controls stay in one scan line.
        query = SimpleCardWidget()
        query.setObjectName("DatasetQueryBar")
        q = QHBoxLayout(query)
        q.setContentsMargins(10, 7, 10, 7)
        q.setSpacing(7)

        q.addWidget(StrongBodyLabel("当前视图"))
        self.status = QComboBox()
        self.status.addItems(["全部状态", "推荐", "备选", "淘汰"])
        self.eligibility = QComboBox()
        self.eligibility.addItems(["全部判定", "可直接用", "需复核", "硬淘汰"])
        self.scale = QComboBox()
        self.scale.addItems(["全部景别", "头肩", "半身", "全身"])
        self.angle = QComboBox()
        self.angle.addItems(["全部角度", "正脸", "3/4", "侧脸"])
        self.sort = QComboBox()
        self.sort.addItems(["质量优先", "原始顺序", "FIQA", "BRISQUE", "清晰度"])
        for widget in (self.status, self.eligibility, self.scale, self.angle, self.sort):
            widget.setMinimumWidth(108)
            q.addWidget(widget)

        self.best_only = QCheckBox("重复组只看最佳")
        q.addWidget(self.best_only)
        q.addStretch(1)

        # Advanced / low-frequency features no longer occupy their own rows.
        self.saved_view = TransparentPushButton("视图")
        self.extreme = TransparentPushButton("极值")
        self.more = TransparentPushButton("更多…")
        self.more.setToolTip("保存视图 / AI 审核包 / 导入建议 / 其他低频工具")
        q.addWidget(self.saved_view)
        q.addWidget(self.extreme)
        q.addWidget(self.more)
        root.addWidget(query)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)

        # Gallery is the dominant workspace.
        gallery_card = SimpleCardWidget()
        gl = QVBoxLayout(gallery_card)
        gl.setContentsMargins(10, 9, 10, 8)
        gl.setSpacing(6)

        gallery_head = QHBoxLayout()
        gallery_head.addWidget(StrongBodyLabel("数据集"))
        gallery_head.addWidget(chip("推荐 96", "#dcefe2", "#2f6f44"))
        gallery_head.addWidget(chip("备选 51", "#fff0cc", "#8a5d00"))
        gallery_head.addWidget(chip("淘汰 28", "#efd6d8", "#8c2f39"))
        gallery_head.addStretch(1)
        self.view_summary = CaptionLabel("显示 175 / 175")
        self.view_summary.setStyleSheet("color:#69727d;")
        gallery_head.addWidget(self.view_summary)
        gl.addLayout(gallery_head)

        self.gallery = GalleryList()
        gl.addWidget(self.gallery, 1)

        footer = QHBoxLayout()
        self.shortcut = CaptionLabel("中键 推荐↔备选   ·   右键双击 淘汰")
        self.shortcut.setStyleSheet("color:#8a9199;")
        footer.addWidget(self.shortcut)
        footer.addStretch(1)
        self.prev = TransparentPushButton("上一页")
        self.page = CaptionLabel("1 / 3")
        self.page.setAlignment(Qt.AlignCenter)
        self.page.setMinimumWidth(50)
        self.next = PushButton("下一页")
        footer.addWidget(self.prev)
        footer.addWidget(self.page)
        footer.addWidget(self.next)
        gl.addLayout(footer)
        self.main_splitter.addWidget(gallery_card)

        # A single contextual inspector replaces the rejected tall card stack.
        inspector = SimpleCardWidget()
        inspector.setObjectName("DatasetInspectorV2")
        inspector.setMinimumWidth(390)
        inspector.setMaximumWidth(520)
        il = QVBoxLayout(inspector)
        il.setContentsMargins(10, 10, 10, 10)
        il.setSpacing(8)

        selected_head = QHBoxLayout()
        selected_head.addWidget(StrongBodyLabel("当前图片"))
        selected_head.addStretch(1)
        self.open_original = TransparentPushButton("打开原图")
        selected_head.addWidget(self.open_original)
        il.addLayout(selected_head)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(265)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setStyleSheet(
            "background:#eef1f4; border:1px solid #d9dfe5; border-radius:10px;"
        )
        il.addWidget(self.preview, 1)

        file_row = QHBoxLayout()
        self.file_name = StrongBodyLabel("danielle_0147.jpg")
        file_row.addWidget(self.file_name, 1)
        self.status_chip = chip("推荐", "#dcefe2", "#2f6f44")
        self.eligibility_chip = chip("PASS", "#e9f1fb", "#356a9a")
        file_row.addWidget(self.status_chip)
        file_row.addWidget(self.eligibility_chip)
        il.addLayout(file_row)

        # Contextual image-level tools sit next to the selected image context.
        image_tools = QHBoxLayout()
        self.manual_composite = TransparentPushButton("手动组合图拆分…")
        self.manual_composite.setToolTip("仅分析当前选中图片")
        image_tools.addWidget(self.manual_composite)
        image_tools.addStretch(1)
        self.sample_id = CaptionLabel("sample-0147")
        self.sample_id.setStyleSheet("color:#8a9199;")
        image_tools.addWidget(self.sample_id)
        il.addLayout(image_tools)

        # Tabs replace vertical card stacking.
        tabs = QWidget()
        tab_layout = QHBoxLayout(tabs)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(4)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons = []
        for index, name in enumerate(("概览", "分析", "审核")):
            b = PushButton(name)
            b.setCheckable(True)
            b.setMinimumHeight(34)
            b.setChecked(index == 0)
            self.tab_group.addButton(b, index)
            tab_layout.addWidget(b)
            self.tab_buttons.append(b)
        il.addWidget(tabs)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._overview_page())
        self.stack.addWidget(self._analysis_page())
        self.stack.addWidget(self._review_page())
        il.addWidget(self.stack)
        self.tab_group.idClicked.connect(self.stack.setCurrentIndex)
        self.tab_group.idClicked.connect(lambda _id: self._sync_tab_styles())

        # Manual status is persistent and close to the selected image.
        state_sep = QLabel()
        state_sep.setFixedHeight(1)
        state_sep.setStyleSheet("background:#e3e7eb;")
        il.addWidget(state_sep)
        state_head = QHBoxLayout()
        state_head.addWidget(StrongBodyLabel("人工状态"))
        state_head.addStretch(1)
        self.restore_auto = TransparentPushButton("恢复自动")
        state_head.addWidget(self.restore_auto)
        il.addLayout(state_head)

        state_row = QHBoxLayout()
        self.manual_group = QButtonGroup(self)
        self.manual_group.setExclusive(True)
        self.rec_btn = PushButton("推荐")
        self.backup_btn = PushButton("备选")
        self.reject_btn = PushButton("淘汰")
        for b in (self.rec_btn, self.backup_btn, self.reject_btn):
            b.setCheckable(True)
            self.manual_group.addButton(b)
            state_row.addWidget(b)
        self.rec_btn.setChecked(True)
        self.manual_group.idClicked.connect(lambda _id: self._sync_manual_styles())
        il.addLayout(state_row)

        self.main_splitter.addWidget(inspector)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setSizes([1220, 420])
        root.addWidget(self.main_splitter, 1)

        self.setStyleSheet(
            "QDialog#DatasetReviewLayoutV2 { background:#f4f6f8; color:#1f2328; }"
            "QSplitter::handle { background:rgba(0,0,0,14); }"
            "QSplitter::handle:hover { background:rgba(0,120,212,95); }"
        )

    @staticmethod
    def _set_checked_style(button, checked, *, accent="#e7f2ff", text="#175f96", border="#6aa7e8"):
        button.setStyleSheet(
            (
                f"background:{accent}; color:{text}; border:1px solid {border}; "
                "font-weight:700; border-radius:6px;"
            )
            if checked
            else ""
        )

    def _sync_target_styles(self):
        for button in self.target_group.buttons():
            self._set_checked_style(button, button.isChecked())

    def _sync_tab_styles(self):
        for button in self.tab_buttons:
            self._set_checked_style(button, button.isChecked())

    def _sync_manual_styles(self):
        styles = {
            self.rec_btn: ("#dcefe2", "#2f6f44", "#75b88a"),
            self.backup_btn: ("#fff0cc", "#8a5d00", "#d3ad58"),
            self.reject_btn: ("#efd6d8", "#8c2f39", "#c57d84"),
        }
        for button, (bg, fg, border) in styles.items():
            self._set_checked_style(
                button,
                button.isChecked(),
                accent=bg,
                text=fg,
                border=border,
            )

    def _overview_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 4, 2, 2)
        layout.setSpacing(8)

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(18)
        metric_grid.setVerticalSpacing(7)
        metrics = [
            ("分辨率", "2048 × 3072"),
            ("景别", "半身"),
            ("水平角度", "正脸"),
            ("俯仰", "正常"),
            ("FIQA", "0.683"),
            ("BRISQUE", "24.6"),
            ("清晰度", "116.4"),
            ("主脸占比", "26.8%"),
        ]
        for row, (name, value) in enumerate(metrics):
            col = (row % 2) * 2
            r = row // 2
            label = CaptionLabel(name)
            label.setStyleSheet("color:#7a838d;")
            metric_grid.addWidget(label, r, col)
            metric_grid.addWidget(StrongBodyLabel(value), r, col + 1)
        layout.addLayout(metric_grid)

        reason_title = StrongBodyLabel("为什么推荐")
        layout.addWidget(reason_title)
        reason = CaptionLabel("通过基础门槛，并补足「半身 × 正脸」覆盖")
        reason.setWordWrap(True)
        reason.setStyleSheet(
            "background:#eef4fb; color:#365f87; border-radius:8px; padding:8px;"
        )
        layout.addWidget(reason)
        layout.addStretch(1)
        return page

    def _analysis_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 4, 2, 2)
        layout.setSpacing(7)
        rows = [
            ("人脸检测", "1 张独立人脸 · 主脸置信度 0.973"),
            ("主脸尺寸", "548 px · 占画面 26.8%"),
            ("姿态", "yaw 1.8° · pitch -2.6° · roll 0.7°"),
            ("亮度", "126.7"),
            ("重复组", "第 18 组 · 组内 2 / 4"),
            ("复核标记", "无"),
            ("硬淘汰", "无"),
        ]
        for title, value in rows:
            row = QHBoxLayout()
            name = CaptionLabel(title)
            name.setStyleSheet("color:#7a838d;")
            name.setMinimumWidth(84)
            row.addWidget(name)
            val = QLabel(value)
            val.setWordWrap(True)
            row.addWidget(val, 1)
            layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _review_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 4, 2, 2)
        layout.setSpacing(8)
        layout.addWidget(StrongBodyLabel("AI 审核建议"))
        suggestion = CaptionLabel(
            "建议维持推荐。脸部质量稳定；与当前数据集中同造型图片相比，"
            "这张在正脸与半身覆盖上仍有边际价值。"
        )
        suggestion.setWordWrap(True)
        suggestion.setStyleSheet(
            "background:#f0f3f6; border-radius:8px; padding:9px;"
        )
        layout.addWidget(suggestion)
        buttons = QHBoxLayout()
        buttons.addWidget(PrimaryPushButton("接受建议"))
        buttons.addWidget(PushButton("拒绝"))
        buttons.addWidget(TransparentPushButton("清除"))
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def _populate(self):
        statuses = ["推荐", "推荐", "备选", "推荐", "淘汰", "推荐", "备选"]
        for i in range(30):
            state = statuses[i % len(statuses)]
            pix = make_thumb(i)
            item = QListWidgetItem(QIcon(pix), f"{i+1:03d} · {state}")
            item.setData(Qt.UserRole, state)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setToolTip(
                f"danielle_{i+1:04d}.jpg\n"
                f"{state} · {'PASS' if state != '淘汰' else 'REJECT'}"
            )
            self.gallery.addItem(item)
        self.gallery.setCurrentRow(7)
        self.preview.setPixmap(
            make_thumb(7, (520, 390)).scaled(
                QSize(420, 315), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    font_path = os.environ.get("DATASET_V2_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    dialog = DatasetReviewLayoutV2()
    dialog.show()
    for _ in range(8):
        app.processEvents()

    # Structural guards: this v2 must not regress to #84's stacked inspector.
    assert dialog.main_splitter.sizes()[0] > dialog.main_splitter.sizes()[1] * 2
    assert dialog.stack.count() == 3
    assert dialog.stack.currentIndex() == 0
    assert all(button.isCheckable() for button in dialog.tab_buttons)
    assert dialog.tab_buttons[0].isChecked()
    assert dialog.rec_btn.isChecked()
    assert dialog.manual_composite.parent() is not None
    assert dialog.more.toolTip()
    assert dialog.gallery.count() == 30
    assert dialog.gallery.currentRow() == 7

    # Tabs keep one information layer visible at a time.
    dialog.tab_buttons[1].click()
    app.processEvents()
    assert dialog.stack.currentIndex() == 1
    dialog.tab_buttons[2].click()
    app.processEvents()
    assert dialog.stack.currentIndex() == 2
    dialog.tab_buttons[0].click()
    app.processEvents()
    assert dialog.stack.currentIndex() == 0

    path = args.out / "dataset_review_layout_v2.png"
    assert dialog.grab().save(str(path)), path
    print(path)
    dialog.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
