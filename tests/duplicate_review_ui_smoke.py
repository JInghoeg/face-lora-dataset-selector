"""Real-Qt production smoke for the approved Duplicate Review v0.4 UI."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "ui" / "qt" / "duplicate_review.py"
SPEC = importlib.util.spec_from_file_location("duplicate_review_under_test", MODULE_PATH)
duplicate_review = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(duplicate_review)
DuplicateReviewDialog = duplicate_review.DuplicateReviewDialog


@dataclass
class FakeRecord:
    sample_id: str
    path: Path
    status: str
    duplicate_group: int
    width: int
    height: int
    file_size: int
    face_quality: float
    brisque: float
    blur: float
    person_scale: str
    angle_class: str
    eligibility: str = "PASS"
    duplicate_ignore: bool = False
    manual_status: str | None = None


class FakeBackend:
    duplicate_ignored_group_id = -1

    def __init__(self, reviewed=None):
        self.reviewed = set(reviewed or ())

    def duplicate_group_ids(self, records):
        return sorted(
            {
                r.duplicate_group
                for r in records
                if r.duplicate_group and not r.duplicate_ignore
            }
        )

    def duplicate_group_members(self, records, group_id):
        if group_id == self.duplicate_ignored_group_id:
            return [r for r in records if r.duplicate_ignore]
        return [
            r
            for r in records
            if r.duplicate_group == group_id and not r.duplicate_ignore
        ]

    def duplicate_group_reviewed(self, records, group_id):
        return group_id in self.reviewed

    def duplicate_keep_best(self, records, group_id):
        members = self.duplicate_group_members(records, group_id)
        if not members:
            return False
        for index, record in enumerate(members):
            record.status = "推荐" if index == 0 else "淘汰"
        self.reviewed.add(group_id)
        return True

    def duplicate_apply_checked(self, records, group_id, selected):
        members = self.duplicate_group_members(records, group_id)
        if not members:
            return False
        for record in members:
            record.status = "推荐" if record.sample_id in selected else "淘汰"
        if group_id != self.duplicate_ignored_group_id:
            self.reviewed.add(group_id)
        return True

    def duplicate_apply_all_groups(self, records, selected):
        for record in records:
            if not record.duplicate_ignore and record.duplicate_group:
                record.status = "推荐" if record.sample_id in selected else "淘汰"
        self.reviewed.update(self.duplicate_group_ids(records))
        return True

    def duplicate_keep_all(self, records, group_id):
        members = self.duplicate_group_members(records, group_id)
        if not members:
            return False
        for record in members:
            record.status = "推荐"
        if group_id != self.duplicate_ignored_group_id:
            self.reviewed.add(group_id)
        return True

    def duplicate_restore_auto(self, records, group_id):
        members = self.duplicate_group_members(records, group_id)
        if not members:
            return False
        for record in members:
            record.status = "备选"
        self.reviewed.discard(group_id)
        return True

    def duplicate_set_ignored(self, records, selected, ignored):
        changed = False
        for record in records:
            if record.sample_id in selected and record.duplicate_ignore != ignored:
                record.duplicate_ignore = ignored
                changed = True
        return changed


def make_image(path: Path, size: tuple[int, int], seed: int):
    w, h = size
    image = Image.new("RGB", (w, h), (230 - seed * 4, 220, 205 + seed * 2))
    draw = ImageDraw.Draw(image)
    margin = max(18, int(min(w, h) * 0.08))
    draw.rounded_rectangle(
        (margin, margin, w - margin, h - margin),
        radius=max(16, margin // 2),
        fill=(190 - seed * 2, 170 + seed, 155 + seed * 3),
    )
    cx, cy = w // 2, int(h * 0.40)
    radius = max(28, int(min(w, h) * 0.18))
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(242, 214 - seed, 196),
    )
    image.save(path)


def make_records(root: Path, target_count: int):
    shapes = [
        (720, 1080),
        (1280, 720),
        (900, 900),
        (720, 1080),
        (1200, 800),
        (800, 1200),
        (1280, 720),
        (900, 1200),
        (1400, 780),
        (800, 800),
    ]
    counts = [3, 5, target_count, 3, 6, 4, 2, 5, 3, 4, 3, 5, 4, 2, 6, 4, 3, 5]
    scales = ["近景/头肩", "半身", "大半身", "全身"]
    angles = ["正脸", "左3/4", "右3/4", "左侧脸", "右侧脸"]
    records = []
    serial = 0
    for group_id, count in enumerate(counts, 1):
        for member in range(count):
            w, h = shapes[member % len(shapes)]
            path = root / f"group_{group_id:02d}_{member:02d}.png"
            make_image(path, (w, h), (serial + member) % 10)
            records.append(
                FakeRecord(
                    sample_id=f"g{group_id:02d}-{member:02d}",
                    path=path,
                    status="推荐" if member == 0 else "备选",
                    duplicate_group=group_id,
                    width=w,
                    height=h,
                    file_size=1_300_000 + serial * 17_000,
                    face_quality=0.86 - member * 0.025,
                    brisque=24.0 + member * 2.1,
                    blur=118.0 - member * 4.0,
                    person_scale=scales[member % len(scales)],
                    angle_class=angles[member % len(angles)],
                )
            )
            serial += 1
    return records


def pump(app, count=8):
    for _ in range(count):
        app.processEvents()


def select_group(dialog, group_id):
    for row in range(dialog.group_list.count()):
        item = dialog.group_list.item(row)
        if item.data(Qt.UserRole) == group_id:
            dialog.group_list.setCurrentRow(row)
            dialog.show_group(item)
            return row
    raise AssertionError(f"group {group_id} not found")


def build_dialog(root: Path, target_count: int):
    backend = FakeBackend(reviewed={1, 2})
    records = make_records(root, target_count)
    changed = []
    dialog = DuplicateReviewDialog(
        backend,
        records,
        lambda regroup: changed.append(regroup),
    )
    return dialog, backend, changed


def render_case(out_dir: Path, target_count: int):
    with tempfile.TemporaryDirectory() as td:
        dialog, _backend, _changed = build_dialog(Path(td), target_count)
        dialog.show()
        app = QApplication.instance()
        pump(app)
        select_group(dialog, 3)
        pump(app)
        if hasattr(dialog.members, "reflow"):
            dialog.members.reflow()
        pump(app)

        assert dialog._fluent is not None
        assert dialog.top_close_button is not None
        assert dialog.close_button is not None
        assert dialog.main_splitter is not None
        bottom_height = dialog.main_splitter.sizes()[1]
        assert 120 <= bottom_height <= 180, bottom_height
        assert (
            dialog.group_list.viewport().height()
            < dialog.group_list.gridSize().height() * 2
        ), "default navigator must expose one thumbnail row only"

        path = out_dir / f"duplicate_review_production_{target_count}_mixed.png"
        assert dialog.grab().save(str(path)), path
        dialog.close()
        pump(app)
        return path


def assert_auto_advance():
    with tempfile.TemporaryDirectory() as td:
        dialog, backend, _changed = build_dialog(Path(td), 4)
        dialog.show()
        app = QApplication.instance()
        pump(app)
        select_group(dialog, 3)
        pump(app)

        dialog.keep_checked()
        pump(app)
        assert dialog.current_group == 4, dialog.current_group
        assert 3 in backend.reviewed

        select_group(dialog, 18)
        pump(app)
        dialog.keep_checked()
        pump(app)
        assert dialog.current_group == 18, dialog.current_group
        assert 18 in backend.reviewed

        dialog.close()
        pump(app)


def assert_fallback_starts():
    original = duplicate_review._load_fluent
    duplicate_review._load_fluent = lambda: None
    try:
        with tempfile.TemporaryDirectory() as td:
            backend = FakeBackend(reviewed={1, 2})
            records = make_records(Path(td), 4)
            dialog = DuplicateReviewDialog(backend, records, lambda _regroup: None)
            assert dialog._fluent is None
            assert dialog.top_close_button is None
            dialog.close()
            QApplication.instance().processEvents()
    finally:
        duplicate_review._load_fluent = original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])

    font_path = os.environ.get("DUPLICATE_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    assert_auto_advance()
    assert_fallback_starts()
    print("duplicate auto-advance: PASS")
    print("duplicate no-Fluent fallback: PASS")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for count in (4, 6, 10):
            print(render_case(args.out, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
