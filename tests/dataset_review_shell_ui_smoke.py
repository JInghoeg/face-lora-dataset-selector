"""Production smoke for the v0.4 main Dataset Review shell."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication

import app
from core.models import Photo
from ui.qt import DatasetReviewPane


def make_photo(index: int):
    status = ("推荐", "备选", "淘汰")[index % 3]
    eligibility = ("PASS", "REVIEW", "REJECT")[index % 3]
    photo = Photo(
        Path(f"sample_{index:02d}.jpg"),
        sample_id=f"sample-{index:02d}",
        auto_status=status,
        eligibility=eligibility,
    )
    photo.width = 1024
    photo.height = 1365
    photo.face_quality = 0.55 + index * 0.01
    photo.brisque = 25.0 + index
    photo.blur = 70.0 + index
    photo.face_px = 420
    photo.face_ratio = 0.22
    photo.person_scale = "半身"
    photo.angle_class = "正脸"
    photo.pitch_class = "正常"
    return photo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    qapp = QApplication.instance() or QApplication([])

    font_path = os.environ.get("DATASET_REVIEW_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                qapp.setFont(QFont(families[0], 10))

    events = []
    pane = DatasetReviewPane(
        previous_callback=lambda: events.append("prev"),
        next_callback=lambda: events.append("next"),
        manual_callback=lambda value: events.append(("manual", value)),
        restore_callback=lambda: events.append("restore"),
        accept_ai_callback=lambda: events.append("accept-ai"),
        reject_ai_callback=lambda: events.append("reject-ai"),
        clear_ai_callback=lambda: events.append("clear-ai"),
    )
    assert pane.fluent_enabled, "production Fluent Dataset Review shell was not loaded"
    assert pane.dataset_splitter.handleWidth() >= 8
    assert not pane.dataset_splitter.childrenCollapsible()
    assert pane.inspector_scroll.widgetResizable()
    assert pane.inspector_scroll.widget() is pane.inspector

    pane.prev.click()
    pane.next.click()
    pane.manual_status_buttons[0].click()
    pane.restore_btn.click()
    pane.accept_ai_btn.click()
    pane.reject_ai_btn.click()
    pane.clear_ai_btn.click()
    assert events == [
        "prev",
        "next",
        ("manual", "推荐"),
        "restore",
        "accept-ai",
        "reject-ai",
        "clear-ai",
    ]

    pane.resize(1000, 560)
    pane.show()
    qapp.processEvents()
    before = pane.dataset_splitter.sizes()
    pane.dataset_splitter.setSizes([560, 420])
    qapp.processEvents()
    after = pane.dataset_splitter.sizes()
    assert after != before, (before, after)
    assert after[1] > 300, after

    # Real Window integration: aliases used by existing behavior remain wired to
    # the extracted pane and live translation still updates card titles.
    window = app.Window()
    assert window.review_pane.fluent_enabled
    assert window.grid is window.review_pane.grid
    assert window.dataset_model is window.review_pane.dataset_model
    assert window.stat_box is window.review_pane.stat_box
    assert window.analysis_box is window.review_pane.analysis_box
    assert window.manual_box is window.review_pane.manual_box
    assert window.ai_box is window.review_pane.ai_box
    assert window.stat_box.title() == "统计（点击分类筛选）"
    assert window.analysis_box.title() == "图片分析数据"
    assert window.manual_box.title() == "人工状态（优先于自动结果）"
    assert window.ai_box.title() == "AI 审核建议"

    records = [make_photo(i) for i in range(18)]
    window.records = records
    for index, photo in enumerate(records):
        pixmap = QPixmap(150, 150)
        pixmap.fill(QColor(220 - index * 3, 225, 232))
        window.thumb_memory[app.key(photo.path)] = pixmap
    window.refresh()
    qapp.processEvents()
    assert window.dataset_model.rowCount() == len(records)

    # Inspector remains independently scrollable rather than forcing the whole
    # gallery/sidebar layout beyond the window height.
    window.resize(1120, 620)
    window.show()
    qapp.processEvents()
    scroll = window.review_pane.inspector_scroll.verticalScrollBar()
    assert scroll.maximum() > 0, scroll.maximum()

    # Stable sample-id selection remains owned by the proven DatasetListModel.
    second = window.dataset_model.index(1, 0)
    window.grid.setCurrentIndex(second)
    assert window.selected() is records[1]

    if args.out:
        assert window.grab().save(str(args.out / "dataset_review_shell.png"))

    window.close()
    pane.close()
    qapp.processEvents()
    print("Dataset Review Fluent shell smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
