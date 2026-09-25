"""Offscreen regression for the main Dataset View Model/View seam."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

import app
from core.models import Photo
from ui.qt import DatasetListModel, DatasetListView, DatasetViewRow


qapp = QApplication.instance() or QApplication([])

pixmap = QPixmap(150, 150)
pixmap.fill(QColor("#e8edf2"))
icon = QIcon(pixmap)

model = DatasetListModel()
model.set_rows(
    [
        DatasetViewRow(
            record_index=7,
            sample_id="sample-7",
            text="x.jpg",
            tooltip="tip",
            icon=icon,
            background=QColor("#d9f4df"),
        )
    ]
)
index = model.index(0, 0)
assert model.rowCount() == 1
assert model.data(index, Qt.ItemDataRole.DisplayRole) == "x.jpg"
assert model.record_index(index) == 7
assert model.sample_id(index) == "sample-7"
assert model.update_icon("sample-7", 99, icon)
assert not model.data(index, Qt.ItemDataRole.DecorationRole).isNull()

view = DatasetListView()
view.setModel(model)
view.setCurrentIndex(index)
assert view.currentIndex().isValid()

window = app.Window()
a = Photo(Path("a.jpg"), sample_id="sample-a", auto_status="推荐", eligibility="PASS")
b = Photo(Path("b.jpg"), sample_id="sample-b", auto_status="备选", eligibility="REVIEW")
window.records = [a, b]
window.thumb_memory[app.key(a.path)] = pixmap
window.thumb_memory[app.key(b.path)] = pixmap
window.refresh()

assert isinstance(window.grid, DatasetListView)
assert isinstance(window.dataset_model, DatasetListModel)
assert window.dataset_model.rowCount() == 2
first = window.dataset_model.index(0, 0)
second = window.dataset_model.index(1, 0)
assert window.dataset_model.sample_id(first) == "sample-a"
assert window.dataset_model.sample_id(second) == "sample-b"

window.grid.setCurrentIndex(second)
assert window.selected() is b

# Stable identity wins over a stale record_index carried by a visual row.
window.dataset_model.set_rows(
    [
        DatasetViewRow(
            record_index=0,
            sample_id="sample-b",
            text="b.jpg",
            tooltip="tip",
            icon=icon,
            background=QColor("#fff2bf"),
        )
    ]
)
stable = window.dataset_model.index(0, 0)
assert window.view_record_index(stable) == 1
assert window.record_from_view(stable) is b

window.close()
view.close()
print("Dataset View Model/View offscreen smoke OK")
