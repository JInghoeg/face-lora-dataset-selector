"""Production Auto Crop Fluent Filmstrip smoke."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QWheelEvent
from PySide6.QtWidgets import QApplication, QListView

import app
from core.models import Photo
from features.auto_crop.service import AutoCropProposal, FEATURE_KEY, PROPOSAL_VERSION


def make_image(path: Path, seed: int):
    image = Image.new("RGB", (960, 720), (48 + seed * 8, 58, 72))
    draw = ImageDraw.Draw(image)
    draw.ellipse((250, 80, 700, 610), fill=(165, 125 + seed * 4, 108))
    draw.rectangle((320, 260, 640, 700), fill=(76, 112, 154))
    image.save(path)


def make_record(path: Path, decision: str, edited: bool, offset: int):
    photo = Photo(path)
    photo.sample_id = f"smoke-{path.stem}"
    photo.auto_status = "推荐"
    try:
        stat = path.stat()
        photo.file_size = stat.st_size
        photo.mtime_ns = stat.st_mtime_ns
    except Exception:
        pass

    auto_box = [190 + offset, 60, 770 - offset, 690]
    box = [220 + offset, 80, 740 - offset, 665] if edited else list(auto_box)
    proposal = AutoCropProposal(
        auto_box=auto_box,
        box=box,
        decision=decision,
        auto_removed_area_ratio=0.22,
        removed_area_ratio=0.30 if edited else 0.22,
        alpha_min=0.10,
        padding_px=32,
        warnings=[],
        manually_adjusted=edited,
        image_size=[960, 720],
    )
    photo.feature_state[FEATURE_KEY] = {
        "version": PROPOSAL_VERSION,
        "state": "candidate",
        "proposal": proposal.to_dict(),
    }
    return photo


def build_records(root: Path):
    rows = []
    states = [
        ("pending", False),
        ("accepted", True),
        ("keep_original", False),
    ]
    # Enough candidates to force multiple wrapped rows so the production
    # candidate grid's vertical scrolling/resizing is exercised.
    for i in range(12):
        decision, edited = states[i % len(states)]
        path = root / f"candidate_{i:02d}.png"
        make_image(path, i)
        rows.append(
            make_record(
                path,
                decision,
                edited,
                (i % 3) * 20,
            )
        )
    return rows


def wait_thumbnails(qapp, dialog, timeout=8.0):
    deadline = time.time() + timeout
    while len(dialog.thumb_icons) < len(dialog.records) and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.03)
    qapp.processEvents()
    assert len(dialog.thumb_icons) == len(dialog.records), (
        len(dialog.thumb_icons),
        len(dialog.records),
    )


def verify_filmstrip_navigation(qapp, dialog):
    qapp.processEvents()

    assert dialog.items.isWrapping()
    assert dialog.items.horizontalScrollBar().maximum() == 0

    # At the default compact height, exactly one candidate row should be
    # visible while additional wrapped rows overflow vertically.
    grid_h = dialog.items.gridSize().height()
    viewport_h = dialog.items.viewport().height()

    # Judge the real laid-out item geometry rather than a fixed pixel margin:
    # row 1 must be fully visible and row 2 must start outside the viewport.
    rects = [
        dialog.items.visualItemRect(dialog.items.item(row))
        for row in range(dialog.items.count())
    ]
    row_tops = sorted({rect.top() for rect in rects if rect.isValid()})
    assert len(row_tops) >= 2, row_tops
    first_top, second_top = row_tops[:2]
    first_bottom = max(rect.bottom() for rect in rects if rect.top() == first_top)
    assert first_bottom < viewport_h, (first_bottom, viewport_h, grid_h)
    assert second_top >= viewport_h, (second_top, viewport_h, grid_h)

    vbar = dialog.items.verticalScrollBar()
    compact_max = vbar.maximum()
    assert compact_max > 0, compact_max

    # A normal wheel event should scroll the candidate grid vertically.
    vbar.setValue(0)
    center = QPointF(
        dialog.items.viewport().width() / 2,
        dialog.items.viewport().height() / 2,
    )
    wheel = QWheelEvent(
        center,
        center,
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(dialog.items.viewport(), wheel)
    qapp.processEvents()
    assert vbar.value() > 0, (vbar.value(), vbar.maximum())

    # Dragging the splitter upward must reveal more wrapped rows and therefore
    # reduce the remaining vertical scroll range.
    before = dialog.main_splitter.sizes()
    dialog.main_splitter.setSizes([420, 360])
    qapp.processEvents()
    after = dialog.main_splitter.sizes()
    expanded_max = vbar.maximum()
    assert after[1] > before[1], (before, after)
    assert after[0] < before[0], (before, after)
    assert expanded_max < compact_max, (compact_max, expanded_max)


def verify_roi(qapp, dialog):
    assert dialog.roi_preview.roi is not None

    # The reviewer must see the complete source boundary and every resize
    # handle, including when a proposal touches an image edge.
    x_range, y_range = dialog.roi_preview.view.viewRange()
    w, h = dialog.roi_preview.image_size
    assert x_range[0] < 0 and x_range[1] > w, (x_range, w)
    assert y_range[0] < 0 and y_range[1] > h, (y_range, h)
    assert len(dialog.roi_preview.roi.handles) == 8, len(dialog.roi_preview.roi.handles)
    pixel_x, pixel_y = dialog.roi_preview.view.viewPixelSize()
    assert abs(pixel_x - pixel_y) <= max(pixel_x, pixel_y) * 0.01, (
        pixel_x,
        pixel_y,
    )

    # Horizontal comparison panes need an obvious, usable splitter rather than
    # two effectively fixed cards.
    assert dialog.work_splitter.handleWidth() >= 8
    assert not dialog.work_splitter.childrenCollapsible()
    before_split = dialog.work_splitter.sizes()
    dialog.work_splitter.setSizes([600, 700])
    qapp.processEvents()
    after_split = dialog.work_splitter.sizes()
    assert after_split != before_split, (before_split, after_split)
    assert after_split[1] > before_split[1], (before_split, after_split)

    # Reflowing the horizontal panes must keep the complete source visible.
    qapp.processEvents()
    x_range, y_range = dialog.roi_preview.view.viewRange()
    assert x_range[0] < 0 and x_range[1] > w, (x_range, w)
    assert y_range[0] < 0 and y_range[1] > h, (y_range, h)
    pixel_x, pixel_y = dialog.roi_preview.view.viewPixelSize()
    assert abs(pixel_x - pixel_y) <= max(pixel_x, pixel_y) * 0.01, (
        pixel_x,
        pixel_y,
    )

    before = dialog.roi_preview.box()
    edited = [before[0] + 8, before[1] + 6, before[2] - 10, before[3] - 8]
    dialog.roi_preview.set_box(edited)
    qapp.processEvents()
    assert dialog.roi_preview.box() == edited
    dialog.roi_finished(edited)

    current = dialog.records[dialog.current]
    proposal = app.BACKEND.auto_crop_proposal(current)
    assert proposal.box == edited
    assert proposal.manually_adjusted
    assert proposal.decision == "pending"

    dialog.reset_auto_box()
    proposal = app.BACKEND.auto_crop_proposal(current)
    assert proposal.box == proposal.auto_box
    assert not proposal.manually_adjusted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    qapp = QApplication.instance() or QApplication([])

    font_path = os.environ.get("AUTO_CROP_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                qapp.setFont(QFont(families[0], 10))
                print("UI font:", families[0])

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        records = build_records(root)
        cache = root / "thumbs"
        changed = []

        dialog = app.AutoCropReviewDialog(
            app.BACKEND,
            records,
            lambda: changed.append(True),
            cache,
        )
        dialog.show()
        qapp.processEvents()

        assert dialog._fluent is not None, "production Fluent UI was not loaded"
        assert dialog.windowTitle() == "自动裁剪复核"
        assert dialog.windowFlags() & Qt.FramelessWindowHint
        assert dialog.items.viewMode() == QListView.ViewMode.IconMode
        assert dialog.items.flow() == QListView.Flow.LeftToRight
        assert dialog.items.count() == 12
        assert dialog.theme_button is not None

        wait_thumbnails(qapp, dialog)

        # Native-lifetime regression: candidate navigation must reuse the same
        # RectROI and the same 8 pyqtgraph Handle wrappers. Recreating handles
        # per image caused Windows-native GC/Shiboken access violations after
        # sustained review.
        roi_identity = id(dialog.roi_preview.roi)
        handle_identities = tuple(
            id(handle) for handle in dialog.roi_preview.roi.getHandles()
        )
        assert len(handle_identities) == 8
        for cycle in range(80):
            row = cycle % dialog.items.count()
            item = dialog.items.item(row)
            dialog.show_item(item)
            qapp.processEvents()
            assert id(dialog.roi_preview.roi) == roi_identity
            assert tuple(
                id(handle) for handle in dialog.roi_preview.roi.getHandles()
            ) == handle_identities

        # Native IconMode must render a real thumbnail cell rather than the
        # compressed row delegate used by QFluentWidgets ListWidget.
        qapp.processEvents()
        first_rect = dialog.items.visualItemRect(dialog.items.item(0))
        assert first_rect.height() >= 120, first_rect
        for row in range(dialog.items.count()):
            assert not dialog.items.item(row).icon().isNull()

        verify_filmstrip_navigation(qapp, dialog)

        # Stable sample-id selection, not transient row identity.
        second = dialog.items.item(1)
        expected_id = second.data(Qt.UserRole)
        dialog.show_item(second)
        assert dialog.current_sample_id == expected_id
        assert dialog.records[dialog.current].sample_id == expected_id

        verify_roi(qapp, dialog)

        # Capture real production light mode.
        dialog.apply_theme("light")
        qapp.processEvents()
        time.sleep(0.18)
        qapp.processEvents()
        assert dialog._preferred_theme == "light"
        if args.out:
            assert dialog.grab().save(str(args.out / "auto_crop_fluent_light.png"))

        # Top-right control toggles to coherent scoped dark mode. QFluent card
        # backgrounds animate for ~120 ms, so capture only after the transition.
        dialog.toggle_theme()
        qapp.processEvents()
        time.sleep(0.22)
        qapp.processEvents()
        assert dialog._preferred_theme == "dark"
        assert "#202020" in dialog.styleSheet()
        assert "QScrollBar:vertical" in dialog.styleSheet()
        assert "background:#686868" in dialog.styleSheet()
        if args.out:
            assert dialog.grab().save(str(args.out / "auto_crop_fluent_dark.png"))

        # Decision behavior and automatic forward movement remain intact.
        current = dialog.records[dialog.current]
        dialog.set_decision("accepted")
        assert app.BACKEND.auto_crop_proposal(current).decision == "accepted"
        assert dialog._decision_in_flight
        qapp.processEvents()
        assert not dialog._decision_in_flight
        assert changed

        dialog.reject()  # cleanup / restore prior global Fluent theme
        qapp.processEvents()

    print("Auto Crop Fluent Filmstrip production smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
