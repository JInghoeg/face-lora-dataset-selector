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


class FluentAutoCropReviewDialog(app.AutoCropReviewDialog):
    """Test-only Fluent layout variants using the real Auto Crop workflow."""

    def __init__(self, records, changed, *, layout_mode="side_browser", dark=False, parent=None):
        self.layout_mode = layout_mode
        self.dark = dark
        super().__init__(records, changed, parent)

    def _fluent_common(self):
        from qfluentwidgets import (
            BodyLabel,
            CaptionLabel,
            ListWidget,
            PrimaryPushButton,
            PushButton,
            SimpleCardWidget,
            StrongBodyLabel,
            TransparentPushButton,
        )
        return {
            "BodyLabel": BodyLabel,
            "CaptionLabel": CaptionLabel,
            "ListWidget": ListWidget,
            "PrimaryPushButton": PrimaryPushButton,
            "PushButton": PushButton,
            "SimpleCardWidget": SimpleCardWidget,
            "StrongBodyLabel": StrongBodyLabel,
            "TransparentPushButton": TransparentPushButton,
        }

    def _decision_bar(self, api):
        from PySide6.QtWidgets import QHBoxLayout

        actions = QHBoxLayout()
        actions.setSpacing(8)
        accept = api["PrimaryPushButton"]("接受当前裁剪框")
        accept.clicked.connect(lambda: self.set_decision("accepted"))
        reset = api["PushButton"]("重置为自动建议")
        reset.clicked.connect(self.reset_auto_box)
        keep = api["PushButton"]("保留原图")
        keep.clicked.connect(lambda: self.set_decision("keep_original"))
        pending = api["TransparentPushButton"]("恢复待定")
        pending.clicked.connect(lambda: self.set_decision("pending"))
        for button in (accept, reset, keep, pending):
            actions.addWidget(button)
        actions.addStretch(1)
        close = api["TransparentPushButton"]("关闭")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        return actions

    def _roi_card(self, api):
        from PySide6.QtWidgets import QVBoxLayout

        card = api["SimpleCardWidget"]()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(
            api["CaptionLabel"](
                "蓝虚线＝自动建议 ｜ 绿框＝当前裁剪框（可拖动 / 四边四角缩放）"
            )
        )
        self.roi_preview = app.AutoCropROIWidget()
        self.roi_preview.regionChanged.connect(self.roi_changed)
        self.roi_preview.regionChangeFinished.connect(self.roi_finished)
        layout.addWidget(self.roi_preview, 1)
        return card

    def _preview_card(self, api, minimum=300):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel, QVBoxLayout

        card = api["SimpleCardWidget"]()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(api["StrongBodyLabel"]("当前裁剪结果"))
        self.crop_preview = QLabel()
        self.crop_preview.setAlignment(Qt.AlignCenter)
        self.crop_preview.setMinimumSize(minimum, minimum)
        layout.addWidget(self.crop_preview, 1)
        return card

    def _list_widget(self, api, minimum_width=260):
        self.items = api["ListWidget"]()
        self.items.setMinimumWidth(minimum_width)
        self.items.itemClicked.connect(self.show_item)
        return self.items

    def ui(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QScrollArea,
            QSplitter,
            QVBoxLayout,
            QWidget,
        )

        api = self._fluent_common()
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.info = api["BodyLabel"]("选择 Auto Crop 候选")
        self.info.setWordWrap(True)

        if self.layout_mode == "filmstrip":
            # Mature photo-editor pattern: large viewer, inspector on the right,
            # collection browser as a shallow bottom filmstrip.
            top = QSplitter(Qt.Horizontal)
            top.addWidget(self._roi_card(api))

            inspector = api["SimpleCardWidget"]()
            il = QVBoxLayout(inspector)
            il.setContentsMargins(10, 10, 10, 10)
            il.setSpacing(8)
            il.addWidget(api["StrongBodyLabel"]("裁剪信息"))
            il.addWidget(self.info)
            il.addWidget(self._preview_card(api, minimum=260), 1)
            top.addWidget(inspector)
            top.setSizes([980, 360])
            root.addWidget(top, 1)

            film = api["SimpleCardWidget"]()
            fl = QHBoxLayout(film)
            fl.setContentsMargins(10, 8, 10, 8)
            fl.setSpacing(8)
            fl.addWidget(api["StrongBodyLabel"]("候选"))
            self.items = self._list_widget(api, minimum_width=0)
            self.items.setFlow(self.items.LeftToRight)
            self.items.setWrapping(False)
            self.items.setMaximumHeight(130)
            fl.addWidget(self.items, 1)
            root.addWidget(film)
            root.addLayout(self._decision_bar(api))
            return

        if self.layout_mode == "single_viewer":
            # darktable-style crop emphasis: full image is the crop surface;
            # metadata/decisions live in a compact inspector, no large duplicate
            # crop preview permanently consuming half the canvas.
            split = QSplitter(Qt.Horizontal)
            split.addWidget(self._roi_card(api))

            inspector = api["SimpleCardWidget"]()
            il = QVBoxLayout(inspector)
            il.setContentsMargins(12, 12, 12, 12)
            il.setSpacing(10)
            il.addWidget(api["StrongBodyLabel"]("Auto Crop 复核"))
            il.addWidget(self.info)
            il.addWidget(api["CaptionLabel"]("裁剪结果随绿色 ROI 实时更新"))
            self.crop_preview = self._preview_card(api, minimum=220).findChild(
                __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
            )
            # Use a compact preview card as inspector evidence, not a second viewer.
            compact = self._preview_card(api, minimum=220)
            il.addWidget(compact)
            il.addStretch(1)
            il.addLayout(self._decision_bar(api))
            split.addWidget(inspector)
            split.setSizes([1080, 330])
            root.addWidget(split, 1)

            film = api["SimpleCardWidget"]()
            fl = QHBoxLayout(film)
            fl.setContentsMargins(10, 8, 10, 8)
            self.items = self._list_widget(api, minimum_width=0)
            self.items.setFlow(self.items.LeftToRight)
            self.items.setWrapping(False)
            self.items.setMaximumHeight(110)
            fl.addWidget(self.items, 1)
            root.addWidget(film)
            return

        # Side-browser pattern: browser on the left, large crop editor center,
        # compact inspector/preview on the right.
        split = QSplitter(Qt.Horizontal)

        browser = api["SimpleCardWidget"]()
        bl = QVBoxLayout(browser)
        bl.setContentsMargins(10, 10, 10, 10)
        bl.setSpacing(8)
        bl.addWidget(api["StrongBodyLabel"]("Auto Crop 候选"))
        bl.addWidget(self._list_widget(api, minimum_width=250), 1)
        split.addWidget(browser)

        split.addWidget(self._roi_card(api))

        inspector = api["SimpleCardWidget"]()
        il = QVBoxLayout(inspector)
        il.setContentsMargins(10, 10, 10, 10)
        il.setSpacing(8)
        il.addWidget(api["StrongBodyLabel"]("当前图片"))
        il.addWidget(self.info)
        il.addWidget(self._preview_card(api, minimum=280), 1)
        il.addLayout(self._decision_bar(api))
        split.addWidget(inspector)

        split.setSizes([250, 820, 330])
        root.addWidget(split, 1)



def render_fluent_variant(records, output: Path, dark: bool, layout_mode: str) -> None:
    from qfluentwidgets import Theme, setTheme

    setTheme(Theme.DARK if dark else Theme.LIGHT)
    dialog = FluentAutoCropReviewDialog(
        records,
        lambda: None,
        layout_mode=layout_mode,
        dark=dark,
    )
    dialog.resize(1450, 860)

    if dark:
        # Test-only coherence proof: make ordinary Qt container surfaces match
        # the Fluent dark palette without starting a production theme system.
        dialog.setStyleSheet(
            "QDialog, QWidget { background: #202020; color: #f2f2f2; } "
            "QLabel { color: #f2f2f2; }"
        )

    dialog.show()
    QApplication.processEvents()
    verify_roi(dialog)
    QApplication.processEvents()
    image = dialog.grab()
    if image.isNull():
        raise RuntimeError("failed to grab Fluent dialog")
    if not image.save(str(output)):
        raise RuntimeError(f"failed to save {output}")
    dialog.close()
    QApplication.processEvents()



def render_qdarkstyle_variant(records, output: Path, dark: bool) -> None:
    import qdarkstyle
    from qdarkstyle.light.palette import LightPalette

    dialog = app.AutoCropReviewDialog(records, lambda: None)
    dialog.resize(1450, 860)
    if dark:
        dialog.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())
    else:
        dialog.setStyleSheet(
            qdarkstyle.load_stylesheet(qt_api="pyside6", palette=LightPalette)
        )
    dialog.show()
    QApplication.processEvents()
    verify_roi(dialog)
    QApplication.processEvents()
    image = dialog.grab()
    if image.isNull():
        raise RuntimeError("failed to grab QDarkStyle dialog")
    if not image.save(str(output)):
        raise RuntimeError(f"failed to save {output}")
    dialog.close()
    QApplication.processEvents()


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
    from PySide6.QtGui import QFont, QFontDatabase

    font_path = os.environ.get("AUTO_CROP_VISUAL_FONT")
    chosen = None
    if font_path and Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                chosen = families[0]

    if not chosen:
        families = set(QFontDatabase.families())
        preferred = [
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Microsoft JhengHei UI",
            "Microsoft JhengHei",
            "SimHei",
        ]
        chosen = next((name for name in preferred if name in families), None)

    if chosen:
        qapp.setFont(QFont(chosen, 10))
    print("UI font:", chosen or qapp.font().family())

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

        fluent_variants = [
            ("fluent_side_browser", False, "side_browser"),
            ("fluent_filmstrip", False, "filmstrip"),
            ("fluent_single_viewer", False, "single_viewer"),
            ("fluent_dark_coherence", True, "side_browser"),
        ]
        for name, dark, layout_mode in fluent_variants:
            records = build_records(Path(td))
            path = args.out / f"{name}.png"
            render_fluent_variant(records, path, dark, layout_mode)
            outputs.append(path)

        for name, dark in (("qdarkstyle_light", False), ("qdarkstyle_dark", True)):
            records = build_records(Path(td))
            path = args.out / f"{name}.png"
            render_qdarkstyle_variant(records, path, dark)
            outputs.append(path)

    make_contact_sheet(outputs, args.out / "contact_sheet.png")
    print("Auto Crop UI spike render OK")
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
