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
from PySide6.QtCore import Qt
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
    specs = [
        ("pending.png", "pending", False, 0),
        ("accepted.png", "accepted", True, 20),
        ("keep.png", "keep_original", False, 40),
    ]
    for i, (name, decision, edited, offset) in enumerate(specs):
        path = root / name
        make_image(path, i)
        rows.append(make_record(path, decision, edited, offset))
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


def verify_roi(qapp, dialog):
    assert dialog.roi_preview.roi is not None
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
        assert dialog.items.viewMode() == QListView.ViewMode.IconMode
        assert dialog.items.flow() == QListView.Flow.LeftToRight
        assert dialog.items.count() == 3
        assert dialog.theme_button is not None

        wait_thumbnails(qapp, dialog)
        for row in range(dialog.items.count()):
            assert not dialog.items.item(row).icon().isNull()

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
        assert dialog._preferred_theme == "light"
        if args.out:
            assert dialog.grab().save(str(args.out / "auto_crop_fluent_light.png"))

        # Top-right control toggles to coherent scoped dark mode.
        dialog.toggle_theme()
        qapp.processEvents()
        assert dialog._preferred_theme == "dark"
        assert "#202020" in dialog.styleSheet()
        if args.out:
            assert dialog.grab().save(str(args.out / "auto_crop_fluent_dark.png"))

        # Decision behavior and automatic forward movement remain intact.
        current = dialog.records[dialog.current]
        dialog.set_decision("accepted")
        assert app.BACKEND.auto_crop_proposal(current).decision == "accepted"
        assert changed

        dialog.reject()  # cleanup / restore prior global Fluent theme
        qapp.processEvents()

    print("Auto Crop Fluent Filmstrip production smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
