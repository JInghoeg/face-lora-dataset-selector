"""Real-Qt smoke for the accepted v0.4 Composite Split production UI."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ui.qt.composite_split_review import CompositeSplitReviewDialog


@dataclass
class FakeRecord:
    sample_id: str
    path: Path
    composite_proposal: object
    status: str = "推荐"
    composite_scan_version: int = 2


class FakeBackend:
    composite_proposal_version = 2

    def make_composite_proposal(self, **kwargs):
        defaults = {
            "mode": "split_people",
            "output_boxes": [],
            "baseline_boxes": [],
            "manual_triggered": False,
            "decision": "pending",
            "detail": "",
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)


def proposal(boxes, *, decision="pending", manual=False, mode="split_people"):
    boxes = [list(box) for box in boxes]
    return SimpleNamespace(
        mode=mode,
        output_boxes=boxes,
        baseline_boxes=[list(box) for box in boxes],
        manual_triggered=manual,
        decision=decision,
        detail="",
    )


def make_image(path: Path, seed: int):
    image = Image.new("RGB", (1600, 1000), (226 - seed * 3, 224, 216))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 700, 1600, 1000), fill=(175, 184, 176))
    centers = (330, 800, 1260)
    colors = ((86, 128, 168), (168, 104, 114), (94, 150, 118))
    for index, cx in enumerate(centers):
        draw.ellipse(
            (cx - 72, 180, cx + 72, 324),
            fill=(239, 207 - index * 4, 188),
        )
        draw.rounded_rectangle(
            (cx - 105, 330, cx + 105, 760),
            radius=50,
            fill=colors[index],
        )
    image.save(path)


def records(root: Path):
    specs = [
        (
            "auto-pending",
            proposal(
                [(140, 160, 610, 920), (860, 160, 1420, 930)],
                decision="pending",
            ),
        ),
        (
            "manual-pending",
            proposal(
                [
                    (120, 160, 520, 940),
                    (590, 150, 1010, 930),
                    (1080, 165, 1470, 940),
                ],
                decision="pending",
                manual=True,
            ),
        ),
        (
            "accepted",
            proposal([(240, 150, 1350, 930)], decision="accepted", mode="group_crop"),
        ),
        (
            "rejected",
            proposal([(200, 150, 1380, 930)], decision="rejected", mode="group_crop"),
        ),
        (
            "manual-zero",
            proposal([], decision="pending", manual=True),
        ),
    ]
    result = []
    for index, (sample_id, value) in enumerate(specs, 1):
        path = root / f"{sample_id}.png"
        make_image(path, index)
        result.append(FakeRecord(sample_id, path, value))
    return result


def pump(app, count=8):
    for _ in range(count):
        app.processEvents()


def build_dialog(root: Path):
    backend = FakeBackend()
    rs = records(root)
    changed = []
    materialized = []

    def redetect(record):
        return proposal(
            [
                (130, 160, 510, 930),
                (600, 150, 1000, 925),
                (1090, 170, 1460, 930),
            ],
            manual=True,
        )

    dialog = CompositeSplitReviewDialog(
        backend,
        rs,
        lambda: changed.append("changed"),
        lambda record, keep: materialized.append((record.sample_id, list(keep))) or True,
        root / "thumbs",
        focus_record=rs[1],
        redetect_current=redetect,
    )
    return dialog, rs, changed, materialized


def assert_core_interactions():
    with tempfile.TemporaryDirectory() as td:
        dialog, rs, changed, _materialized = build_dialog(Path(td))
        app = QApplication.instance()
        dialog.show()
        pump(app)

        assert dialog.current == 1
        assert dialog.redetect_button.isVisible()
        assert dialog.reset_button.isVisible() and dialog.reset_button.isEnabled()
        assert dialog.delete_button.isVisible() and dialog.delete_button.isEnabled()
        assert dialog.outputs.count() == 3

        # Right output card -> current box.
        dialog.select_box(1)
        pump(app)
        assert dialog.selected_box == 1
        assert dialog.outputs.currentRow() == 1

        # Reset only the selected box to its own baseline.
        p = rs[1].composite_proposal
        box1 = tuple(p.output_boxes[0])
        box2_baseline = tuple(p.baseline_boxes[1])
        box3 = tuple(p.output_boxes[2])
        p.output_boxes[1] = [30, 30, 260, 260]
        dialog.reset_current_box()
        pump(app)
        assert tuple(p.output_boxes[0]) == box1
        assert tuple(p.output_boxes[1]) == box2_baseline
        assert tuple(p.output_boxes[2]) == box3

        # Delete only the current box/output.
        dialog.delete_current_box()
        pump(app)
        assert len(p.output_boxes) == 2
        assert tuple(p.output_boxes[0]) == box1
        assert tuple(p.output_boxes[1]) == box3
        assert dialog.outputs.count() == 2

        # Automatic candidates share direct-create/reset/delete behavior.
        dialog.items.setCurrentRow(0)
        dialog.show_row(0)
        pump(app)
        assert not dialog.redetect_button.isVisible()
        auto = rs[0].composite_proposal
        before = len(auto.output_boxes)
        dialog.roi_preview.boxCreated.emit([40, 40, 300, 280])
        pump(app)
        assert len(auto.output_boxes) == before + 1
        assert dialog.outputs.count() == before + 1
        assert dialog.reset_button.isEnabled()
        assert dialog.delete_button.isEnabled()

        # Zero-box manual recovery: all three tools coexist; reset/delete disabled.
        dialog.items.setCurrentRow(4)
        dialog.show_row(4)
        pump(app)
        assert dialog.redetect_button.isVisible()
        assert dialog.reset_button.isVisible() and not dialog.reset_button.isEnabled()
        assert dialog.delete_button.isVisible() and not dialog.delete_button.isEnabled()
        assert not dialog.accept_button.isEnabled()
        assert dialog.outputs.count() == 0

        dialog.redetect_current()
        pump(app)
        assert len(rs[4].composite_proposal.output_boxes) == 3
        assert dialog.redetect_button.isVisible()
        assert dialog.reset_button.isEnabled()
        assert dialog.delete_button.isEnabled()
        assert dialog.accept_button.isEnabled()

        # Candidate navigation is three-state, with selection separate from state.
        colors = {}
        for row in (1, 2, 3):
            item = dialog.items.item(row)
            colors[item.data(Qt.UserRole + 1)] = item.data(Qt.BackgroundRole).name()
        assert len(set(colors.values())) == 3, colors

        # Default one row, expand upward on splitter drag.
        compact_h = dialog.items.viewport().height()
        grid_h = dialog.items.gridSize().height()
        assert compact_h <= grid_h + 4, (compact_h, grid_h)
        sizes = dialog.main_splitter.sizes()
        dialog.main_splitter.setSizes([max(1, sizes[0] - 180), sizes[1] + 180])
        dialog._sync_candidate_expansion()
        pump(app)
        assert dialog.items.maximumHeight() > 1000

        assert changed
        dialog.close()
        pump(app)


def render(out_dir: Path, theme: str):
    with tempfile.TemporaryDirectory() as td:
        dialog, _rs, _changed, _materialized = build_dialog(Path(td))
        app = QApplication.instance()
        dialog.apply_theme(theme)
        dialog.show()
        pump(app)
        dialog.items.setCurrentRow(1)
        dialog.show_row(1)
        pump(app)
        path = out_dir / f"composite_review_production_manual_{theme}.png"
        assert dialog.grab().save(str(path)), path
        dialog.close()
        pump(app)
        return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])

    font_path = os.environ.get("COMPOSITE_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    assert_core_interactions()
    print("Composite production interactions: PASS")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        print(render(args.out, args.theme))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
