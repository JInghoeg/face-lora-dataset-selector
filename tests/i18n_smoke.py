"""Permanent i18n infrastructure smoke.

Exercises the real global language selector and an already-open Auto Crop
production dialog.  Switching language must not mutate dataset/backend state.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QAbstractButton, QComboBox, QGroupBox, QLabel, QWidget

import app
from core.models import AnalysisFinding, Photo
from features.auto_crop.service import AutoCropProposal, FEATURE_KEY, PROPOSAL_VERSION
from ui.i18n import initialize_i18n


def build_record(root: Path) -> Photo:
    path = root / "i18n_auto_crop.png"
    Image.new("RGB", (640, 480), (90, 110, 140)).save(path)

    photo = Photo(path)
    photo.sample_id = "i18n-auto-crop"
    photo.auto_status = "推荐"
    photo.width = 640
    photo.height = 480
    photo.faces = 1
    photo.person_scale = "近景/头肩"
    photo.angle_class = "正脸"
    photo.pitch_class = "正常"
    photo.face_quality = 0.20
    photo.brisque = 30.0
    photo.blur = 60.0
    photo.face_px = 180
    photo.face_ratio = 0.08
    photo.eligibility = "REVIEW"
    photo.review_flags = [
        AnalysisFinding(
            "low_face_quality",
            "ediffiqa",
            0.20,
            0.25,
            "eDifFIQA 人脸质量偏低",
        )
    ]
    photo.recommendation_reasons = [
        "自动推荐：通过基础门槛，并用于补足 近景/头肩 / 正脸 覆盖"
    ]
    proposal = AutoCropProposal(
        auto_box=[80, 40, 560, 450],
        box=[95, 55, 545, 435],
        decision="pending",
        auto_removed_area_ratio=0.20,
        removed_area_ratio=0.25,
        alpha_min=0.10,
        padding_px=32,
        warnings=["subject_mask_touches_source_edge"],
        manually_adjusted=True,
        image_size=[640, 480],
    )
    photo.feature_state[FEATURE_KEY] = {
        "version": PROPOSAL_VERSION,
        "state": "candidate",
        "proposal": proposal.to_dict(),
    }
    return photo


HAN = re.compile(r"[\u4e00-\u9fff]")


def assert_no_han(*values):
    leaked = [value for value in values if HAN.search(str(value))]
    assert not leaked, f"Chinese leaked into English UI: {leaked}"


def visible_widget_texts(root):
    values = []
    for widget in [root, *root.findChildren(QWidget)]:
        if hasattr(widget, "isVisible") and not widget.isVisible():
            continue
        if isinstance(widget, QAbstractButton):
            values.append(widget.text())
        elif isinstance(widget, QLabel):
            values.append(widget.text())
        elif isinstance(widget, QGroupBox):
            values.append(widget.title())
        elif isinstance(widget, QComboBox):
            # Only the current display is visible. The language selector
            # intentionally contains the native name “简体中文” in its menu.
            values.append(widget.currentText())
        if hasattr(widget, "toolTip"):
            tooltip = widget.toolTip()
            if tooltip:
                values.append(tooltip)
    return [value for value in values if value]


def select_language(window, code: str):
    index = window.language_combo.findData(code)
    assert index >= 0, code
    window.language_combo.setCurrentIndex(index)
    QApplication.processEvents()


def main() -> int:
    qapp = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        settings_path = root / "ui.ini"
        manager = initialize_i18n(
            qapp,
            settings_path=settings_path,
            translations_dir=ROOT / "translations",
        )
        assert manager.language == "zh_CN"

        window = app.Window()
        window.show()
        qapp.processEvents()

        assert window.windowTitle() == "LoRA 数据集筛选与字幕清理"
        assert window.tabs.tabText(window.dataset_tab_index) == "LoRA 数据集筛选"
        assert window.duplicate_review_btn.text() == "重复组 复核…"
        assert window.composite_btn.text() == "组合图拆分 复核…"
        assert window.organizer_btn.text() == "整理源文件…"
        assert window.language_combo.currentData() == "zh_CN"

        duplicate_dialog = app.DuplicateReviewDialog(
            app.BACKEND,
            [],
            lambda _regroup=False: None,
            window,
        )
        duplicate_dialog.show()
        qapp.processEvents()
        assert duplicate_dialog.windowTitle() == "重复组人工复核"
        assert duplicate_dialog.group_label.text() == "当前没有重复组"

        record = build_record(root)
        original_state = copy.deepcopy(record.feature_state)
        dialog = app.AutoCropReviewDialog(
            app.BACKEND,
            [record],
            lambda: None,
            root / "thumbs",
            window,
        )
        dialog.show()
        qapp.processEvents()

        assert dialog.windowTitle() == "自动裁剪复核"
        assert dialog.accept_button.text() == "接受当前裁剪框"
        original_sample_id = dialog.current_sample_id
        original_box = list(dialog.roi_preview.box())

        # Exercise the actual global UI selector while the dialog stays open.
        select_language(window, "en_US")
        assert manager.language == "en_US"
        assert window.windowTitle() == "LoRA Dataset Selector & Text Cleanup"
        assert window.tabs.tabText(window.dataset_tab_index) == "LoRA Dataset Selector"
        assert window.duplicate_review_btn.text() == "Duplicate Group Review…"
        assert window.composite_btn.text() == "Composite Split Review…"
        assert window.organizer_btn.text() == "Organize Source Files…"
        assert window.auto_crop_btn.text() == "Auto Crop Review…"

        # The primary product surface must actually be English, not just the
        # shell buttons. Display labels are translated while internal values
        # remain stable for filtering/ranking logic.
        assert window.pick.text() == "Select Image Folder"
        assert window.rescan.text() == "Refresh Folder (F5)"
        assert window.filter_box.title().startswith("1. Filters:")
        assert [window.view_combo.itemText(i) for i in range(window.view_combo.count())] == [
            "All", "Recommended", "Backup", "Rejected"
        ]
        assert app.combo_value(window.view_combo) == "全部"
        assert window.sort_box.title().startswith("2. Sort:")
        assert window.sort_field_combo.currentText() == "Original Order"
        assert app.combo_value(window.sort_field_combo) == "默认顺序"
        assert window.extreme_box.title().startswith("3. Extreme Check:")
        assert window.saved_view_label.text() == "Saved View"
        assert window.stat_box.title().startswith("Statistics")
        assert window.analysis_box.title() == "Image Analysis"
        assert window.manual_box.title().startswith("Manual Status")
        assert window.ai_box.title() == "AI Review Suggestions"

        text_tab = window.sub
        assert text_tab is not None
        assert text_tab.pick_input_btn.text() == "Select Input Folder"
        assert text_tab.scan.text() == "Scan Text"
        assert text_tab.method.currentText() == "AI Repair (MI-GAN)"
        assert text_tab.method.currentData() == "AI 修复（MI-GAN）"
        assert text_tab.view.currentText() == "All Images"
        assert text_tab.view.currentData() == "全部图片"

        # Populate the real main view so dynamic stats, current-view text,
        # thumbnail tooltip and the detail inspector are checked too.
        window.folder = root
        window.records = [record]
        window.refresh()
        qapp.processEvents()
        index = window.dataset_model.index(0, 0)
        assert index.isValid()
        window.grid.setCurrentIndex(index)
        window.details(index)
        qapp.processEvents()
        assert_no_han(
            window.stats.text(),
            window.current_view_label.text(),
            window.detail.text(),
            window.dataset_model.data(index, Qt.ToolTipRole),
        )

        # No visible Chinese presentation text may remain anywhere in the
        # current product shell while English mode is active.
        assert_no_han(
            *visible_widget_texts(window),
            window.tabs.tabText(window.dataset_tab_index),
            window.tabs.tabText(window.text_cleanup_tab_index),
        )

        assert_no_han(
            window.pick.text(),
            window.rescan.text(),
            window.filter_box.title(),
            *(window.view_combo.itemText(i) for i in range(window.view_combo.count())),
            window.sort_box.title(),
            window.extreme_box.title(),
            window.saved_view_label.text(),
            window.stat_box.title(),
            window.analysis_box.title(),
            window.manual_box.title(),
            window.ai_box.title(),
            text_tab.pick_input_btn.text(),
            text_tab.scan.text(),
            text_tab.method.currentText(),
            text_tab.view.currentText(),
        )

        assert duplicate_dialog.windowTitle() == "Duplicate Group Review"
        assert duplicate_dialog.group_label.text() == "No Duplicate Groups"
        assert dialog.windowTitle() == "Auto Crop Review"
        assert dialog.accept_button.text() == "Accept Current Crop"
        assert dialog.keep_button.text() == "Keep Original"
        assert "Status:" in dialog.info.text()
        assert "Subject mask touches the source edge" in dialog.info.text()

        # Locale changes are presentation-only.
        assert record.feature_state == original_state
        assert dialog.current_sample_id == original_sample_id
        assert dialog.roi_preview.box() == original_box

        settings = QSettings(str(settings_path), QSettings.IniFormat)
        assert settings.value("ui/language") == "en_US"

        select_language(window, "zh_CN")
        assert manager.language == "zh_CN"
        assert window.windowTitle() == "LoRA 数据集筛选与字幕清理"
        assert dialog.windowTitle() == "自动裁剪复核"
        assert dialog.accept_button.text() == "接受当前裁剪框"
        assert window.duplicate_review_btn.text() == "重复组 复核…"
        assert window.composite_btn.text() == "组合图拆分 复核…"
        assert window.organizer_btn.text() == "整理源文件…"
        assert window.auto_crop_btn.text() == "自动裁剪 复核…"
        assert window.pick.text() == "选择图片文件夹"
        assert window.filter_box.title() == '1. 筛选：只决定“显示哪些图片”'
        assert window.view_combo.currentText() == "全部"
        assert app.combo_value(window.view_combo) == "全部"
        assert window.sub.pick_input_btn.text() == "选择输入目录"
        assert window.sub.method.currentText() == "AI 修复（MI-GAN）"
        assert window.sub.method.currentData() == "AI 修复（MI-GAN）"
        assert duplicate_dialog.windowTitle() == "重复组人工复核"
        assert duplicate_dialog.group_label.text() == "当前没有重复组"
        assert "状态：" in dialog.info.text()
        assert "主体遮罩触及原图边缘" in dialog.info.text()
        assert record.feature_state == original_state
        assert dialog.current_sample_id == original_sample_id
        assert dialog.roi_preview.box() == original_box

        settings.sync()
        assert settings.value("ui/language") == "zh_CN"

        dialog.close()
        duplicate_dialog.close()
        window.close()
        qapp.processEvents()

    print("Permanent i18n live-switch smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
