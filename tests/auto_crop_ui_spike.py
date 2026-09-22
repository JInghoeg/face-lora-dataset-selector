"""Render the real Auto Crop review dialog under reusable UI candidates.

This is a visual/compatibility spike only. It does not modify production UI.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

import app
from core.models import Photo
from features.auto_crop.service import AutoCropProposal, FEATURE_KEY, PROPOSAL_VERSION


def make_image(path: Path, seed: int) -> None:
    width, height = 960, 720
    image = Image.new("RGB", (width, height), (28 + seed * 8, 36 + seed * 5, 48 + seed * 4))
    draw = ImageDraw.Draw(image)
    # Synthetic subject-like composition: enough visual structure to judge the
    # crop canvas without adding an external fixture or copyrighted asset.
    draw.ellipse((250, 90, 700, 610), fill=(155 + seed * 10, 118, 105))
    draw.rectangle((320, 250, 640, 700), fill=(72, 102 + seed * 8, 142))
    draw.rectangle((0, 590, 960, 720), fill=(68, 78, 86))
    image.save(path)


def make_record(path: Path, *, decision: str, edited: bool, offset: int) -> Photo:
    photo = Photo(path)
    photo.auto_status = "推荐"
    auto_box = [190 + offset, 60, 770 - offset, 690]
    box = [225 + offset, 80, 735 - offset, 665] if edited else list(auto_box)
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
    specs = [
        ("portrait_pending.png", "pending", False, 0),
        ("portrait_accepted.png", "accepted", True, 20),
        ("portrait_keep_original.png", "keep_original", False, 40),
    ]
    records = []
    for i, (name, decision, edited, offset) in enumerate(specs):
        path = root / name
        make_image(path, i)
        records.append(
            make_record(path, decision=decision, edited=edited, offset=offset)
        )
    return records


def verify_roi(dialog: app.AutoCropReviewDialog) -> None:
    assert dialog.records, "synthetic fixture did not enter Auto Crop review"
    assert dialog.roi_preview.roi is not None, "RectROI missing"
    before = dialog.roi_preview.box()
    assert before is not None
    edited = [before[0] + 10, before[1] + 8, before[2] - 12, before[3] - 10]
    dialog.roi_preview.set_box(edited)
    QApplication.processEvents()
    assert dialog.roi_preview.box() == edited

    # Persist through the same backend path used by a finished drag.
    dialog.roi_finished(edited)
    proposal = app.BACKEND.auto_crop_proposal(dialog.records[dialog.current])
    assert proposal is not None
    assert proposal.box == edited
    assert proposal.manually_adjusted
    assert proposal.decision == "pending"

    dialog.reset_auto_box()
    proposal = app.BACKEND.auto_crop_proposal(dialog.records[dialog.current])
    assert proposal is not None
    assert proposal.box == proposal.auto_box
    assert not proposal.manually_adjusted


def render_variant(records, output: Path, theme: str | None) -> None:
    dialog = app.AutoCropReviewDialog(records, lambda: None)
    dialog.resize(1450, 860)

    if theme is not None:
        # Import after PySide6/app so qt-material binds to the existing Qt API.
        from qt_material import apply_stylesheet

        apply_stylesheet(
            dialog,
            theme=f"{theme}.xml",
            invert_secondary=theme.startswith("light_"),
            extra={"density_scale": "-1"},
        )

    dialog.show()
    QApplication.processEvents()
    verify_roi(dialog)
    QApplication.processEvents()
    image = dialog.grab()
    if image.isNull():
        raise RuntimeError(f"failed to grab dialog for {theme or 'baseline'}")
    if not image.save(str(output)):
        raise RuntimeError(f"failed to save {output}")
    dialog.close()
    QApplication.processEvents()


def make_contact_sheet(paths: list[Path], output: Path) -> None:
    images = [Image.open(path).convert("RGB") for path in paths]
    target_w = 760
    resized = []
    for image in images:
        h = round(image.height * target_w / image.width)
        resized.append(image.resize((target_w, h), Image.Resampling.LANCZOS))
    gap = 20
    canvas = Image.new(
        "RGB",
        (target_w, sum(im.height for im in resized) + gap * (len(resized) - 1)),
        "white",
    )
    y = 0
    for image in resized:
        canvas.paste(image, (0, y))
        y += image.height + gap
    canvas.save(output, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    qapp = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as td:
        records = build_records(Path(td))
        variants = [
            ("baseline", None),
            ("material_light_blue", "light_blue"),
            ("material_dark_blue", "dark_blue"),
        ]
        outputs = []
        for name, theme in variants:
            # Rebuild records for each variant because ROI verification mutates state.
            records = build_records(Path(td))
            path = args.out / f"{name}.png"
            render_variant(records, path, theme)
            outputs.append(path)

    make_contact_sheet(outputs, args.out / "contact_sheet.png")
    print("Auto Crop UI spike render OK")
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
