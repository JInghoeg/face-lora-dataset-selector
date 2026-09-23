"""Permanent i18n infrastructure smoke.

Exercises the real global language selector and an already-open Auto Crop
production dialog.  Switching language must not mutate dataset/backend state.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import app
from core.models import Photo
from features.auto_crop.service import AutoCropProposal, FEATURE_KEY, PROPOSAL_VERSION
from ui.i18n import initialize_i18n


def build_record(root: Path) -> Photo:
    path = root / "i18n_auto_crop.png"
    Image.new("RGB", (640, 480), (90, 110, 140)).save(path)

    photo = Photo(path)
    photo.sample_id = "i18n-auto-crop"
    photo.auto_status = "推荐"
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
