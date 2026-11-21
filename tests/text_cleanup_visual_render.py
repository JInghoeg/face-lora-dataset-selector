"""Real-Qt visual render for the actual Text Cleanup SubtitleTab."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
from PIL import Image, ImageDraw
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

from core.models import TextPhoto
from ui.qt import SubtitleTab


class FakeBackend:
    def text_cleanup_load_state(self):
        return SimpleNamespace(
            folder=None,
            output=None,
            method="AI 修复（MI-GAN）",
            expand=3,
            radius=3,
            min_height=0,
            min_area=0,
            min_conf=0.0,
            records=[],
        )

    def text_cleanup_save_state(self, *args, **kwargs):
        return None

    def text_cleanup_eligible(self, record, min_height=0, min_area=0, min_conf=0.0):
        good = []
        for index, box in enumerate(record.boxes):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            height = max(ys) - min(ys)
            area = (max(xs) - min(xs)) * height
            score = record.scores[index] if index < len(record.scores) else 1.0
            if height >= min_height and area >= min_area and score >= min_conf:
                good.append(index)
        return good

    def text_cleanup_ensure_size(self, record):
        return record.height, record.width

    def text_cleanup_load_image(self, path):
        return cv2.imread(str(path), cv2.IMREAD_COLOR)

    def text_cleanup_migan_ready(self):
        return True

    def text_cleanup_repair(self, record, **kwargs):
        return self.text_cleanup_load_image(record.path)


def make_image(path: Path, size, index: int):
    w, h = size
    image = Image.new("RGB", (w, h), (214 - index * 6, 220 - index * 3, 228))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, int(h * 0.68), w, h), fill=(78 + index * 4, 92, 110))
    draw.ellipse((int(w*.34), int(h*.12), int(w*.66), int(h*.48)), fill=(224, 190, 172))
    draw.rounded_rectangle((int(w*.28), int(h*.43), int(w*.72), int(h*.92)), radius=28,
                           fill=(74 + index * 8, 104, 145))
    draw.rectangle((int(w*.54), int(h*.72), int(w*.94), int(h*.82)), fill=(245, 245, 245))
    draw.rectangle((int(w*.16), int(h*.84), int(w*.64), int(h*.91)), fill=(232, 232, 232))
    image.save(path)


def box(x0, y0, x1, y1):
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]


def make_records(root: Path):
    shapes=[(720,960),(960,720),(800,800),(700,980),(1000,700),(760,900)]
    result=[]
    for i,size in enumerate(shapes):
        path=root / f"sample_{i+1:02d}.png"
        make_image(path,size,i)
        w,h=size
        boxes=[]
        selected=[]
        manual=[]
        scores=[]
        suggested=[]
        if i != 4:
            boxes.append(box(int(w*.54),int(h*.72),int(w*.94),int(h*.82)))
            selected.append(i in (0,2,5))
            manual.append(False)
            scores.append(0.94 - i*.03)
            suggested.append(i in (0,2,5))
        if i in (1,2,5):
            boxes.append(box(int(w*.16),int(h*.84),int(w*.64),int(h*.91)))
            selected.append(i in (2,5))
            manual.append(i == 5)
            scores.append(0.86)
            suggested.append(i == 2)
        stat=path.stat()
        result.append(TextPhoto(
            path=path,file_size=stat.st_size,mtime_ns=stat.st_mtime_ns,
            boxes=boxes,selected=selected,manual=manual,scores=scores,
            suggested=suggested,width=w,height=h,
        ))
    return result


def pump(app,count=10):
    for _ in range(count):
        app.processEvents()


def render(out_dir: Path):
    app=QApplication.instance() or QApplication([])
    font_path=os.environ.get("TEXT_CLEANUP_VISUAL_FONT")
    if font_path and Path(font_path).exists():
        font_id=QFontDatabase.addApplicationFont(font_path)
        if font_id >= 0:
            families=QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0],10))

    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        backend=FakeBackend()
        tab=SubtitleTab(backend,ROOT,root/"thumbs")
        tab.folder=root
        tab.input.setText(str(root))
        tab.output=root/"output"
        tab.output_label.setText(str(tab.output))
        tab.records=make_records(root)
        tab.page=0
        tab.resize(1220,780)
        tab.setVisible(True)
        tab.refresh(False)
        pump(app,20)

        first_index=tab.visible[0]
        item=tab.item_by_record[first_index]
        tab.list.setCurrentItem(item)
        tab.show(item)
        pump(app,12)

        out_dir.mkdir(parents=True,exist_ok=True)
        normal=out_dir/"text_cleanup_review.png"
        assert tab.grab().save(str(normal)),normal
        print(normal)

        tab.add.setChecked(True)
        pump(app)
        manual=out_dir/"text_cleanup_manual_draw_active.png"
        assert tab.grab().save(str(manual)),manual
        print(manual)

        tab.close()
        pump(app)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    render(args.out)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
