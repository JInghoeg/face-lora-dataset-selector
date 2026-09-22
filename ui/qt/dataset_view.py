"""Qt Model/View presentation seam for the main Dataset gallery."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QListView


@dataclass(frozen=True)
class DatasetViewRow:
    record_index: int
    sample_id: str
    text: str
    tooltip: str
    icon: QIcon
    background: QColor


class DatasetListModel(QAbstractListModel):
    """Current-page presentation rows; domain filtering/sorting stays outside."""

    RecordIndexRole = int(Qt.ItemDataRole.UserRole) + 1
    SampleIdRole = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[DatasetViewRow] = []
        self._row_by_sample_id: dict[str, int] = {}
        self._row_by_record_index: dict[int, int] = {}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.text
        if role == Qt.ItemDataRole.DecorationRole:
            return row.icon
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.tooltip
        if role == Qt.ItemDataRole.BackgroundRole:
            return row.background
        if role == self.RecordIndexRole:
            return row.record_index
        if role == self.SampleIdRole:
            return row.sample_id
        return None

    def roleNames(self):
        names = dict(super().roleNames())
        names[self.RecordIndexRole] = b"recordIndex"
        names[self.SampleIdRole] = b"sampleId"
        return names

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self._rebuild_lookup()
        self.endResetModel()

    def clear(self):
        if not self._rows:
            return
        self.beginResetModel()
        self._rows = []
        self._row_by_sample_id = {}
        self._row_by_record_index = {}
        self.endResetModel()

    def record_index(self, index):
        value = self.data(index, self.RecordIndexRole)
        return int(value) if value is not None else None

    def sample_id(self, index):
        value = self.data(index, self.SampleIdRole)
        return str(value) if value else ""

    def update_icon(self, sample_id, record_index, icon):
        row_number = self._row_by_sample_id.get(sample_id) if sample_id else None
        if row_number is None:
            row_number = self._row_by_record_index.get(int(record_index))
        if row_number is None or not 0 <= row_number < len(self._rows):
            return False
        old = self._rows[row_number]
        self._rows[row_number] = DatasetViewRow(
            old.record_index,
            old.sample_id,
            old.text,
            old.tooltip,
            icon,
            old.background,
        )
        model_index = self.index(row_number, 0)
        self.dataChanged.emit(
            model_index,
            model_index,
            [Qt.ItemDataRole.DecorationRole],
        )
        return True

    def _rebuild_lookup(self):
        self._row_by_sample_id = {
            row.sample_id: i
            for i, row in enumerate(self._rows)
            if row.sample_id
        }
        self._row_by_record_index = {
            row.record_index: i for i, row in enumerate(self._rows)
        }


class DatasetListView(QListView):
    """Icon-grid QListView preserving the legacy gallery mouse shortcuts."""

    middleIndexClicked = Signal(object)
    rightIndexDoubleClicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setIconSize(QSize(150, 150))
        self.setGridSize(QSize(174, 205))

    def mouseReleaseEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.MiddleButton and index.isValid():
            self.middleIndexClicked.emit(index)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton and index.isValid():
            self.rightIndexDoubleClicked.emit(index)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
