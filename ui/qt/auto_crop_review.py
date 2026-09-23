"""自动裁剪 Qt review presentation.

The feature/backend contract remains outside this module.  QFluentWidgets is an
optional presentation dependency: normal installers/Portable include it, while
source environments without it retain a legacy Qt fallback instead of failing
application startup.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from PySide6.QtCore import QCoreApplication, QEvent, QThread, Qt, Signal, QSize, QRectF
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
import pyqtgraph as pg

from .thumbnail import ThumbnailWorker


def _load_fluent():
    try:
        from qfluentwidgets import (
            BodyLabel,
            CaptionLabel,
            FluentIcon,
            PrimaryPushButton,
            PushButton,
            SimpleCardWidget,
            StrongBodyLabel,
            Theme,
            TransparentPushButton,
            TransparentToolButton,
            isDarkTheme,
            setTheme,
        )
    except ImportError:
        return None
    return {
        "BodyLabel": BodyLabel,
        "CaptionLabel": CaptionLabel,
        "FluentIcon": FluentIcon,
        "PrimaryPushButton": PrimaryPushButton,
        "PushButton": PushButton,
        "SimpleCardWidget": SimpleCardWidget,
        "StrongBodyLabel": StrongBodyLabel,
        "Theme": Theme,
        "TransparentPushButton": TransparentPushButton,
        "TransparentToolButton": TransparentToolButton,
        "isDarkTheme": isDarkTheme,
        "setTheme": setTheme,
    }


class AutoCropROIWidget(QWidget):
    regionChanged = Signal(object)
    regionChangeFinished = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.image_size = (0, 0)
        self.roi = None
        self.auto_outline = None
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = pg.GraphicsLayoutWidget()
        layout.addWidget(self.canvas)
        self.view = self.canvas.addViewBox(lockAspect=True, enableMenu=False)
        self.view.setAspectLocked(True)
        self.view.setMouseEnabled(x=False, y=False)
        self.view.invertY(True)
        self.image_item = pg.ImageItem()
        self.image_item.setOpts(axisOrder="row-major")
        self.view.addItem(self.image_item)
        self.set_theme(False)

    @staticmethod
    def normalized_box(box, image_size):
        w, h = map(int, image_size)
        x0, y0, x1, y1 = map(lambda v: int(round(float(v))), box)
        x0 = max(0, min(max(0, w - 1), x0))
        y0 = max(0, min(max(0, h - 1), y0))
        x1 = max(x0 + 1, min(w, x1))
        y1 = max(y0 + 1, min(h, y1))
        return [x0, y0, x1, y1]

    def set_theme(self, dark):
        self.canvas.setBackground("#171717" if dark else "#f4f5f7")

    def set_data(self, bgr, box, auto_box):
        self._loading = True
        if self.roi is not None:
            self.view.removeItem(self.roi)
            self.roi = None
        if self.auto_outline is not None:
            self.view.removeItem(self.auto_outline)
            self.auto_outline = None

        self.image = bgr
        if bgr is None or not bgr.size:
            self.image_item.clear()
            self.image_size = (0, 0)
            self._loading = False
            return

        h, w = bgr.shape[:2]
        self.image_size = (w, h)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.image_item.setImage(rgb, autoLevels=False, levels=(0, 255))
        self.view.setLimits(xMin=0, xMax=w, yMin=0, yMax=h)
        self.view.setRange(xRange=(0, w), yRange=(0, h), padding=0)

        auto = self.normalized_box(auto_box, (w, h))
        ax0, ay0, ax1, ay1 = auto
        self.auto_outline = pg.PlotCurveItem(
            [ax0, ax1, ax1, ax0, ax0],
            [ay0, ay0, ay1, ay1, ay0],
            pen=pg.mkPen("#4aa3ff", width=2, style=Qt.DashLine),
        )
        self.view.addItem(self.auto_outline)

        current = self.normalized_box(box, (w, h))
        x0, y0, x1, y1 = current
        self.roi = pg.RectROI(
            [x0, y0],
            [x1 - x0, y1 - y0],
            sideScalers=True,
            maxBounds=QRectF(0, 0, w, h),
            movable=True,
            rotatable=False,
            resizable=True,
            removable=False,
            invertible=False,
            scaleSnap=True,
            translateSnap=True,
            snapSize=1,
            pen=pg.mkPen("#32e675", width=2),
        )
        for pos, center in (
            ([0, 0], [1, 1]),
            ([1, 0], [0, 1]),
            ([0, 1], [1, 0]),
            ([0, 0.5], [1, 0.5]),
            ([0.5, 0], [0.5, 1]),
        ):
            self.roi.addScaleHandle(pos, center)
        self.view.addItem(self.roi)
        self.roi.sigRegionChanged.connect(self._changed)
        self.roi.sigRegionChangeFinished.connect(self._finished)
        self._loading = False

    def box(self):
        if self.roi is None:
            return None
        state = self.roi.getState()
        pos = state["pos"]
        size = state["size"]
        return self.normalized_box(
            [pos.x(), pos.y(), pos.x() + size.x(), pos.y() + size.y()],
            self.image_size,
        )

    def set_box(self, box):
        if self.roi is None:
            return
        x0, y0, x1, y1 = self.normalized_box(box, self.image_size)
        self._loading = True
        self.roi.setPos([x0, y0], finish=False)
        self.roi.setSize([x1 - x0, y1 - y0], finish=False)
        self._loading = False
        self.regionChanged.emit([x0, y0, x1, y1])

    def _changed(self, *_):
        if self._loading:
            return
        box = self.box()
        if box:
            self.regionChanged.emit(box)

    def _finished(self, *_):
        if self._loading:
            return
        box = self.box()
        if box:
            self.regionChangeFinished.emit(box)


class AutoCropReviewDialog(QDialog):
    """Production 自动裁剪 review dialog.

    QFluentWidgets presentation is preferred when installed.  Backend methods
    are injected explicitly and remain the source of truth for all decisions.
    """

    _preferred_theme = "light"

    def __init__(self, backend, records, changed, thumbnail_cache, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.records = backend.auto_crop_review_records(records)
        self.changed = changed
        self.thumbnail_cache = Path(thumbnail_cache)
        self.current = -1
        self.current_image = None
        self.current_sample_id = None

        self.thumb_generation = 0
        self.thumb_threads = []
        self.thumb_icons = {}
        self._thumb_token_ids = {}
        self._cleaned = False

        self._fluent = _load_fluent()
        self._initial_global_dark = (
            bool(self._fluent["isDarkTheme"]()) if self._fluent else False
        )
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if self._preferred_theme == "dark"
                else self._fluent["Theme"].LIGHT
            )

        self.setObjectName("AutoCropReviewDialog")
        self.resize(1450, 860)

        if self._fluent:
            self._ui_fluent()
        else:
            self._ui_fallback()

        self.retranslate()
        self.apply_theme(self._preferred_theme)
        self.reload()

    @staticmethod
    def pixmap_from_bgr(img, max_w=520, max_h=440):
        if img is None or not img.size:
            return QPixmap()
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimage = QImage(
            rgb.data,
            w,
            h,
            rgb.strides[0],
            QImage.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(qimage).scaled(
            max_w,
            max_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

    def _ui_fluent(self):
        api = self._fluent
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.header_title = api["StrongBodyLabel"]("")
        header.addWidget(self.header_title)
        header.addStretch(1)
        self.count_label = api["CaptionLabel"]("0 / 0")
        header.addWidget(self.count_label)
        self.theme_button = api["TransparentToolButton"](
            api["FluentIcon"].QUIET_HOURS
        )
        self.theme_button.setFixedSize(36, 32)
        self.theme_button.setIconSize(QSize(16, 16))
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        root.addLayout(header)

        work = QSplitter(Qt.Horizontal)
        self.roi_card = api["SimpleCardWidget"]()
        roi_layout = QVBoxLayout(self.roi_card)
        roi_layout.setContentsMargins(10, 10, 10, 10)
        roi_layout.setSpacing(7)
        self.roi_hint = api["CaptionLabel"]("")
        roi_layout.addWidget(self.roi_hint)
        self.roi_preview = AutoCropROIWidget()
        self.roi_preview.regionChanged.connect(self.roi_changed)
        self.roi_preview.regionChangeFinished.connect(self.roi_finished)
        roi_layout.addWidget(self.roi_preview, 1)
        work.addWidget(self.roi_card)

        self.inspector_card = api["SimpleCardWidget"]()
        inspector_layout = QVBoxLayout(self.inspector_card)
        inspector_layout.setContentsMargins(10, 10, 10, 10)
        inspector_layout.setSpacing(8)
        self.crop_title = api["StrongBodyLabel"]("")
        inspector_layout.addWidget(self.crop_title)
        self.info = api["BodyLabel"]("")
        self.info.setWordWrap(True)
        inspector_layout.addWidget(self.info)
        self.crop_preview = QLabel()
        self.crop_preview.setObjectName("AutoCropCropPreview")
        self.crop_preview.setAlignment(Qt.AlignCenter)
        self.crop_preview.setMinimumSize(300, 300)
        inspector_layout.addWidget(self.crop_preview, 1)
        work.addWidget(self.inspector_card)
        work.setSizes([1010, 360])

        self.filmstrip_card = api["SimpleCardWidget"]()
        film_layout = QVBoxLayout(self.filmstrip_card)
        film_layout.setContentsMargins(8, 6, 8, 8)
        film_layout.setSpacing(4)
        film_head = QHBoxLayout()
        self.candidates_title = api["StrongBodyLabel"]("")
        film_head.addWidget(self.candidates_title)
        film_head.addStretch(1)
        self.film_count = api["CaptionLabel"]("")
        film_head.addWidget(self.film_count)
        film_layout.addLayout(film_head)

        # QFluentWidgets ListWidget is row-oriented and its delegate compresses
        # IconMode thumbnails.  Use Qt's mature native icon view inside the
        # Fluent card so the Filmstrip shows real, useful thumbnails.
        self.items = QListWidget()
        self.items.setObjectName("AutoCropFilmstrip")
        self.items.setViewMode(QListView.ViewMode.IconMode)
        self.items.setFlow(QListView.Flow.LeftToRight)
        self.items.setWrapping(True)
        self.items.setMovement(QListView.Movement.Static)
        self.items.setResizeMode(QListView.ResizeMode.Adjust)
        self.items.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.items.setIconSize(QSize(116, 116))
        self.items.setGridSize(QSize(136, 146))
        self.items.setSpacing(2)
        self.items.setUniformItemSizes(True)
        self.items.setMinimumHeight(116)
        self.items.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.items.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.items.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.items.itemClicked.connect(self.show_item)
        film_layout.addWidget(self.items)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(work)
        self.main_splitter.addWidget(self.filmstrip_card)
        self.main_splitter.setSizes([660, 170])
        root.addWidget(self.main_splitter, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.accept_button = api["PrimaryPushButton"]("")
        self.accept_button.clicked.connect(lambda: self.set_decision("accepted"))
        self.reset_button = api["PushButton"]("")
        self.reset_button.clicked.connect(self.reset_auto_box)
        self.keep_button = api["PushButton"]("")
        self.keep_button.clicked.connect(lambda: self.set_decision("keep_original"))
        self.pending_button = api["TransparentPushButton"]("")
        self.pending_button.clicked.connect(lambda: self.set_decision("pending"))
        for button in (
            self.accept_button,
            self.reset_button,
            self.keep_button,
            self.pending_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        self.close_button = api["TransparentPushButton"]("")
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)
        root.addLayout(actions)

    def _ui_fallback(self):
        root = QVBoxLayout(self)
        split = QSplitter(Qt.Horizontal)
        self.items = QListWidget()
        self.items.setMinimumWidth(330)
        self.items.itemClicked.connect(self.show_item)
        split.addWidget(self.items)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.header_title = None
        self.candidates_title = None
        self.count_label = QLabel("0 / 0")
        self.film_count = QLabel("")
        self.theme_button = None
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("font-weight:600;")
        right_layout.addWidget(self.info)

        previews = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.roi_hint = QLabel("")
        left_layout.addWidget(self.roi_hint)
        self.roi_preview = AutoCropROIWidget()
        self.roi_preview.regionChanged.connect(self.roi_changed)
        self.roi_preview.regionChangeFinished.connect(self.roi_finished)
        left_layout.addWidget(self.roi_preview, 1)
        previews.addWidget(left)

        right_crop = QWidget()
        crop_layout = QVBoxLayout(right_crop)
        self.crop_title = QLabel("")
        crop_layout.addWidget(self.crop_title)
        self.crop_preview = QLabel()
        self.crop_preview.setObjectName("AutoCropCropPreview")
        self.crop_preview.setAlignment(Qt.AlignCenter)
        self.crop_preview.setMinimumSize(430, 430)
        crop_layout.addWidget(self.crop_preview, 1)
        previews.addWidget(right_crop)
        previews.setSizes([680, 520])
        right_layout.addWidget(previews, 1)

        actions = QHBoxLayout()
        self.accept_button = QPushButton("")
        self.accept_button.clicked.connect(lambda: self.set_decision("accepted"))
        self.reset_button = QPushButton("")
        self.reset_button.clicked.connect(self.reset_auto_box)
        self.keep_button = QPushButton("")
        self.keep_button.clicked.connect(lambda: self.set_decision("keep_original"))
        self.pending_button = QPushButton("")
        self.pending_button.clicked.connect(lambda: self.set_decision("pending"))
        for button in (
            self.accept_button,
            self.reset_button,
            self.keep_button,
            self.pending_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        self.close_button = QPushButton("")
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)
        right_layout.addLayout(actions)

        split.addWidget(right)
        split.setSizes([340, 1110])
        root.addWidget(split)

    @staticmethod
    def _tr(source):
        return QCoreApplication.translate("AutoCropReviewDialog", source)

    def retranslate(self):
        self.setWindowTitle(self._tr("自动裁剪复核"))
        if self.header_title is not None:
            self.header_title.setText(self._tr("自动裁剪复核"))
        if self.roi_hint is not None:
            self.roi_hint.setText(
                self._tr(
                    "蓝虚线＝自动建议 ｜ 绿框＝当前裁剪框（可拖动 / 四边四角缩放）"
                )
            )
        if self.crop_title is not None:
            self.crop_title.setText(
                self._tr(
                    "当前裁剪结果"
                    if self._fluent
                    else "当前裁剪结果预览"
                )
            )
        if self.candidates_title is not None:
            self.candidates_title.setText(self._tr("候选"))
        self.accept_button.setText(self._tr("接受当前裁剪框"))
        self.reset_button.setText(self._tr("重置为自动建议"))
        self.keep_button.setText(self._tr("保留原图"))
        self.pending_button.setText(self._tr("恢复待定"))
        self.close_button.setText(self._tr("关闭"))

        self._refresh_translated_dynamic_text()
        self._update_theme_tooltip()

    def _refresh_translated_dynamic_text(self):
        total = len(self.records)
        if self.film_count is not None:
            self.film_count.setText(
                self._tr("{count} 张").format(count=total)
            )

        for row in range(self.items.count()):
            item = self.items.item(row)
            sample_id = item.data(Qt.UserRole)
            _index, record = self._record_by_id(sample_id)
            if record is None:
                continue
            if self._fluent:
                item.setText(self.filmstrip_text(record))
            else:
                item.setText(self.label(record))
            item.setToolTip(self.label(record))

        if not self.records:
            self.info.setText(self._tr("当前没有自动裁剪候选"))
            return

        if self.current >= 0 and self.current < len(self.records):
            record = self.records[self.current]
            proposal = self.backend.auto_crop_proposal(record)
            if proposal is not None and self.current_image is not None:
                box = self.roi_preview.box() or proposal.box
                self.update_info(proposal, box)
            elif proposal is None:
                self.info.setText(self._tr("选择自动裁剪候选"))
        elif self.current < 0:
            self.info.setText(self._tr("选择自动裁剪候选"))

    def _update_theme_tooltip(self):
        if self.theme_button is None:
            return
        dark = self._preferred_theme == "dark"
        self.theme_button.setToolTip(
            self._tr("切换到浅色模式")
            if dark
            else self._tr("切换到深色模式")
        )

    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            self.retranslate()
        super().changeEvent(event)

    def placeholder_icon(self):
        pix = QPixmap(112, 112)
        pix.fill(QColor("#262626" if self._preferred_theme == "dark" else "#eceff3"))
        return QIcon(pix)

    def proposal_state(self, record):
        proposal = self.backend.auto_crop_proposal(record)
        if proposal is None:
            return self._tr("无建议"), ""
        state = {
            "accepted": self._tr("已接受"),
            "keep_original": self._tr("保留原图"),
            "pending": self._tr("待定"),
        }.get(proposal.decision, proposal.decision)
        edited = self._tr(" · 手调") if proposal.manually_adjusted else ""
        return state, edited

    def filmstrip_text(self, record):
        state, edited = self.proposal_state(record)
        name = record.path.name
        if len(name) > 20:
            name = name[:17] + "…"
        return f"{state}{edited}\n{name}"

    def label(self, record):
        proposal = self.backend.auto_crop_proposal(record)
        if proposal is None:
            return record.path.name
        mark = {
            "accepted": "✓",
            "keep_original": "○",
            "pending": "•",
        }.get(proposal.decision, "•")
        state, edited = self.proposal_state(record)
        return (
            f"{mark} {record.path.name}\n"
            + self._tr("{state}{edited} · 去除 {ratio}").format(
                state=state,
                edited=edited,
                ratio=f"{proposal.removed_area_ratio:.1%}",
            )
        )

    def _record_by_id(self, sample_id):
        for index, record in enumerate(self.records):
            if record.sample_id == sample_id:
                return index, record
        return None, None

    def reload(self, select_id=None):
        if select_id is None:
            select_id = self.current_sample_id
        self.records = self.backend.auto_crop_review_records(self.records)
        self.thumb_generation += 1
        self.items.clear()

        placeholder = self.placeholder_icon()
        for record in self.records:
            icon = self.thumb_icons.get(record.sample_id, placeholder)
            if self._fluent:
                item = QListWidgetItem(icon, self.filmstrip_text(record))
            else:
                item = QListWidgetItem(self.label(record))
            item.setData(Qt.UserRole, record.sample_id)
            item.setToolTip(self.label(record))
            self.items.addItem(item)

        total = len(self.records)
        if self.film_count is not None:
            self.film_count.setText(
                self._tr("{count} 张").format(count=total)
            )

        if not self.records:
            self.current = -1
            self.current_sample_id = None
            self.current_image = None
            self.count_label.setText("0 / 0")
            self.info.setText(self._tr("当前没有自动裁剪候选"))
            self.roi_preview.set_data(None, [0, 0, 1, 1], [0, 0, 1, 1])
            self.crop_preview.clear()
            return

        target_row = 0
        if select_id is not None:
            for row, record in enumerate(self.records):
                if record.sample_id == select_id:
                    target_row = row
                    break

        self.items.setCurrentRow(target_row)
        self.show_item(self.items.item(target_row))
        self.start_thumbnails()

    def start_thumbnails(self):
        missing = [
            (index, record)
            for index, record in enumerate(self.records)
            if record.sample_id not in self.thumb_icons
        ]
        if not missing:
            return

        self.thumb_generation += 1
        token = self.thumb_generation
        self._thumb_token_ids[token] = {
            index: record.sample_id for index, record in missing
        }

        thread = QThread()
        worker = ThumbnailWorker(token, missing, self.thumbnail_cache)
        thread._thumbnail_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(self.thumbnail_ready)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self.thumbnail_thread_done(t))
        self.thumb_threads.append(thread)
        thread.start()

    def thumbnail_thread_done(self, thread):
        if thread in self.thumb_threads:
            self.thumb_threads.remove(thread)
        thread.deleteLater()

    def thumbnail_ready(self, token, index, image):
        if token != self.thumb_generation:
            return
        sample_id = self._thumb_token_ids.get(token, {}).get(index)
        if sample_id is None:
            return

        icon = QIcon(QPixmap.fromImage(image))
        self.thumb_icons[sample_id] = icon

        for row in range(self.items.count()):
            item = self.items.item(row)
            if item.data(Qt.UserRole) == sample_id:
                item.setIcon(icon)
                break

    def show_item(self, item):
        if item is None:
            return
        sample_id = item.data(Qt.UserRole)
        index, record = self._record_by_id(sample_id)
        if record is None:
            return
        proposal = self.backend.auto_crop_proposal(record)
        if proposal is None:
            return

        self.current = index
        self.current_sample_id = sample_id
        self.items.setCurrentItem(item)
        self.count_label.setText(f"{index + 1} / {len(self.records)}")

        try:
            with Image.open(record.path) as source:
                try:
                    source.seek(0)
                except EOFError:
                    pass
                source = ImageOps.exif_transpose(source).convert("RGB")
                rgb = np.asarray(source)
            self.current_image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            return

        self.roi_preview.set_data(
            self.current_image,
            proposal.box,
            proposal.auto_box,
        )
        self.update_crop_preview(proposal.box)
        self.update_info(proposal, proposal.box)

    def update_item(self, record):
        for row in range(self.items.count()):
            item = self.items.item(row)
            if item.data(Qt.UserRole) != record.sample_id:
                continue
            if self._fluent:
                item.setText(self.filmstrip_text(record))
            else:
                item.setText(self.label(record))
            item.setToolTip(self.label(record))
            return

    def update_crop_preview(self, box):
        if self.current_image is None:
            return
        h, w = self.current_image.shape[:2]
        x0, y0, x1, y1 = AutoCropROIWidget.normalized_box(box, (w, h))
        crop = self.current_image[y0:y1, x0:x1]
        self.crop_preview.setPixmap(self.pixmap_from_bgr(crop, 360, 360))

    def update_info(self, proposal, box):
        if self.current_image is None or self.current < 0:
            return
        h, w = self.current_image.shape[:2]
        x0, y0, x1, y1 = AutoCropROIWidget.normalized_box(box, (w, h))
        kept = max(0, x1 - x0) * max(0, y1 - y0)
        removed = max(0.0, min(1.0, 1.0 - kept / max(1, w * h)))
        state = {
            "accepted": self._tr("已接受"),
            "keep_original": self._tr("保留原图"),
            "pending": self._tr("待定"),
        }.get(proposal.decision, proposal.decision)
        kind = (
            self._tr("手动调整")
            if list(box) != list(proposal.auto_box)
            else self._tr("自动建议")
        )
        warning = "；".join(proposal.warnings) if proposal.warnings else self._tr("无")
        self.info.setText(
            f"{self.records[self.current].path.name}\n"
            + self._tr(
                "原图 {width} × {height} → 当前 {crop_width} × {crop_height} · 去除 {removed}"
            ).format(
                width=w,
                height=h,
                crop_width=x1 - x0,
                crop_height=y1 - y0,
                removed=f"{removed:.1%}",
            )
            + "\n"
            + self._tr("状态：{state} · 当前框：{kind}").format(
                state=state,
                kind=kind,
            )
            + "\n"
            + self._tr("alpha≥{alpha} · padding {padding}px").format(
                alpha=f"{proposal.alpha_min:.2f}",
                padding=proposal.padding_px,
            )
            + "\n"
            + self._tr("提示：{warning}").format(warning=warning)
        )

    def roi_changed(self, box):
        if self.current < 0:
            return
        proposal = self.backend.auto_crop_proposal(self.records[self.current])
        if proposal is None:
            return
        self.update_crop_preview(box)
        self.update_info(proposal, box)

    def roi_finished(self, box):
        if self.current < 0 or self.current_image is None:
            return
        record = self.records[self.current]
        h, w = self.current_image.shape[:2]
        try:
            proposal = self.backend.update_auto_crop_box(record, box, (w, h))
            self.changed()
            self.update_item(record)
            self.update_crop_preview(proposal.box)
            self.update_info(proposal, proposal.box)
        except Exception as exc:
            proposal = self.backend.auto_crop_proposal(record)
            if proposal is not None:
                self.roi_preview.set_box(proposal.box)
            QMessageBox.warning(self, self._tr("裁剪框无效"), str(exc))

    def reset_auto_box(self):
        if self.current < 0:
            return
        record = self.records[self.current]
        try:
            proposal = self.backend.reset_auto_crop_box(record)
            self.roi_preview.set_box(proposal.box)
            self.changed()
            self.update_item(record)
            self.update_crop_preview(proposal.box)
            self.update_info(proposal, proposal.box)
        except Exception as exc:
            QMessageBox.warning(self, self._tr("无法重置裁剪框"), str(exc))

    def set_decision(self, value):
        if self.current < 0:
            return
        record = self.records[self.current]
        current_index = self.current

        if value == "accepted":
            self.backend.accept_auto_crop(record)
        elif value == "keep_original":
            self.backend.keep_original_auto_crop(record)
        else:
            self.backend.restore_pending_auto_crop(record)

        self.changed()
        next_id = None
        if self.records:
            next_index = min(current_index + 1, len(self.records) - 1)
            next_id = self.records[next_index].sample_id
        self.reload(next_id)

    def toggle_theme(self):
        if not self._fluent:
            return
        new_theme = "dark" if self._preferred_theme != "dark" else "light"
        type(self)._preferred_theme = new_theme
        self.apply_theme(new_theme)

    def apply_theme(self, theme):
        dark = theme == "dark"
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK if dark else self._fluent["Theme"].LIGHT
            )
            if self.theme_button is not None:
                self.theme_button.setIcon(
                    self._fluent["FluentIcon"].BRIGHTNESS
                    if dark
                    else self._fluent["FluentIcon"].QUIET_HOURS
                )
                self._update_theme_tooltip()

        self.roi_preview.set_theme(dark)

        # SimpleCardWidget uses a translucent animated background.  When it is
        # embedded in a plain QDialog (rather than FluentWindow), explicitly
        # synchronize its normal brush to the upstream light/dark values so
        # scoped Dark does not leave light-gray cards behind.
        if self._fluent:
            card_color = QColor(255, 255, 255, 13 if dark else 170)
            for card in (
                self.roi_card,
                self.inspector_card,
                self.filmstrip_card,
            ):
                if hasattr(card, "setBackgroundColor"):
                    card.setBackgroundColor(card_color)
                card.update()

        if dark:
            self.setStyleSheet(
                "QDialog#AutoCropReviewDialog { background:#202020; color:#f2f2f2; }"
                "QLabel#AutoCropCropPreview { background:#171717; "
                "border:1px solid #3a3a3a; border-radius:6px; }"
                "QListWidget#AutoCropFilmstrip { background:transparent; "
                "border:none; outline:none; color:#f2f2f2; }"
                "QListWidget#AutoCropFilmstrip::item { border:1px solid transparent; "
                "border-radius:6px; padding:3px; }"
                "QListWidget#AutoCropFilmstrip::item:hover { "
                "background:rgba(255,255,255,18); }"
                "QListWidget#AutoCropFilmstrip::item:selected { "
                "background:rgba(96,205,255,34); border:1px solid #60cdff; }"
                "QListWidget#AutoCropFilmstrip QScrollBar:vertical { "
                "background:#202020; width:10px; margin:2px 1px 2px 1px; "
                "border:none; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::handle:vertical { "
                "background:#686868; min-height:28px; border-radius:5px; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::handle:vertical:hover { "
                "background:#858585; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::add-line:vertical, "
                "QListWidget#AutoCropFilmstrip QScrollBar::sub-line:vertical { "
                "height:0px; background:transparent; border:none; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::add-page:vertical, "
                "QListWidget#AutoCropFilmstrip QScrollBar::sub-page:vertical { "
                "background:transparent; }"
            )
        else:
            self.setStyleSheet(
                "QDialog#AutoCropReviewDialog { background:#f7f8fa; color:#202020; }"
                "QLabel#AutoCropCropPreview { background:#f1f3f5; "
                "border:1px solid #e0e3e7; border-radius:6px; }"
                "QListWidget#AutoCropFilmstrip { background:transparent; "
                "border:none; outline:none; color:#202020; }"
                "QListWidget#AutoCropFilmstrip::item { border:1px solid transparent; "
                "border-radius:6px; padding:3px; }"
                "QListWidget#AutoCropFilmstrip::item:hover { "
                "background:rgba(0,0,0,10); }"
                "QListWidget#AutoCropFilmstrip::item:selected { "
                "background:rgba(0,120,212,24); border:1px solid #0078d4; }"
                "QListWidget#AutoCropFilmstrip QScrollBar:vertical { "
                "background:#f3f3f3; width:10px; margin:2px 1px 2px 1px; "
                "border:none; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::handle:vertical { "
                "background:#b7b7b7; min-height:28px; border-radius:5px; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::handle:vertical:hover { "
                "background:#969696; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::add-line:vertical, "
                "QListWidget#AutoCropFilmstrip QScrollBar::sub-line:vertical { "
                "height:0px; background:transparent; border:none; }"
                "QListWidget#AutoCropFilmstrip QScrollBar::add-page:vertical, "
                "QListWidget#AutoCropFilmstrip QScrollBar::sub-page:vertical { "
                "background:transparent; }"
            )

        if self._fluent:
            placeholder = self.placeholder_icon()
            for row in range(self.items.count()):
                item = self.items.item(row)
                sample_id = item.data(Qt.UserRole)
                item.setIcon(self.thumb_icons.get(sample_id, placeholder))

    def _cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        self.thumb_generation += 1
        for thread in list(self.thumb_threads):
            thread.requestInterruption()
        for thread in list(self.thumb_threads):
            thread.wait(1500)
        if self._fluent:
            self._fluent["setTheme"](
                self._fluent["Theme"].DARK
                if self._initial_global_dark
                else self._fluent["Theme"].LIGHT
            )

    def done(self, result):
        self._cleanup()
        super().done(result)

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)
