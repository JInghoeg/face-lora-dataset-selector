"""Modern main Dataset Review presentation shell.

This module owns presentation only. Dataset filtering/sorting, recommendation
policy, persistence and file operations remain in Window / SelectorApplication.

The Fluent path follows the already-validated Auto Crop direction while keeping
a native Qt fallback so source environments do not fail merely because the
optional presentation package is absent.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .dataset_view import DatasetListModel, DatasetListView


def _load_fluent():
    try:
        from qfluentwidgets import (
            BodyLabel,
            CaptionLabel,
            PushButton,
            SimpleCardWidget,
            StrongBodyLabel,
            TransparentPushButton,
        )
    except ImportError:
        return None
    return {
        "BodyLabel": BodyLabel,
        "CaptionLabel": CaptionLabel,
        "PushButton": PushButton,
        "SimpleCardWidget": SimpleCardWidget,
        "StrongBodyLabel": StrongBodyLabel,
        "TransparentPushButton": TransparentPushButton,
    }


class ReviewCard(QWidget):
    """Small titled card abstraction with a native Qt fallback."""

    def __init__(self, object_name, parent=None, fluent=None):
        super().__init__(parent)
        self._fluent = fluent
        self.setObjectName(object_name)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.surface = (
            fluent["SimpleCardWidget"]()
            if fluent
            else QFrame()
        )
        self.surface.setObjectName(object_name + "Surface")
        if not fluent:
            self.surface.setFrameShape(QFrame.Shape.StyledPanel)
        outer.addWidget(self.surface)

        self.content_layout = QVBoxLayout(self.surface)
        self.content_layout.setContentsMargins(12, 10, 12, 12)
        self.content_layout.setSpacing(8)

        self.title_label = (
            fluent["StrongBodyLabel"]("")
            if fluent
            else QLabel("")
        )
        if not fluent:
            font = self.title_label.font()
            font.setBold(True)
            self.title_label.setFont(font)
        self.content_layout.addWidget(self.title_label)

    def setTitle(self, text):
        self.title_label.setText(text)

    def title(self):
        return self.title_label.text()


class DatasetReviewPane(QWidget):
    """Gallery + inspector presentation for the main Dataset Selector."""

    def __init__(
        self,
        *,
        parent=None,
        previous_callback=None,
        next_callback=None,
        manual_callback=None,
        restore_callback=None,
        accept_ai_callback=None,
        reject_ai_callback=None,
        clear_ai_callback=None,
    ):
        super().__init__(parent)
        self.setObjectName("DatasetReviewPane")
        self._fluent = _load_fluent()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Current-view / navigation card.
        self.header_card = (
            self._fluent["SimpleCardWidget"]()
            if self._fluent
            else QFrame()
        )
        self.header_card.setObjectName("DatasetReviewHeaderCard")
        if not self._fluent:
            self.header_card.setFrameShape(QFrame.Shape.StyledPanel)
        header = QHBoxLayout(self.header_card)
        header.setContentsMargins(12, 8, 12, 8)
        header.setSpacing(8)

        self.current_view_label = (
            self._fluent["StrongBodyLabel"]("")
            if self._fluent
            else QLabel("")
        )
        self.current_view_label.setWordWrap(True)
        header.addWidget(self.current_view_label, 1)

        self.shortcut_hint = (
            self._fluent["CaptionLabel"]("")
            if self._fluent
            else QLabel("")
        )
        self.shortcut_hint.setWordWrap(False)
        header.addWidget(self.shortcut_hint)

        self.prev = self._button()
        if previous_callback is not None:
            self.prev.clicked.connect(previous_callback)
        header.addWidget(self.prev)

        self.page_label = (
            self._fluent["CaptionLabel"]("")
            if self._fluent
            else QLabel("")
        )
        self.page_label.setMinimumWidth(76)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.page_label)

        self.next = self._button()
        if next_callback is not None:
            self.next.clicked.connect(next_callback)
        header.addWidget(self.next)
        root.addWidget(self.header_card)

        self.dataset_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.dataset_splitter.setObjectName("DatasetWorkSplitter")
        self.dataset_splitter.setChildrenCollapsible(False)
        self.dataset_splitter.setHandleWidth(8)
        self.dataset_splitter.setOpaqueResize(True)

        # Gallery card: keep the proven DatasetListModel / DatasetListView seam.
        self.gallery_card = (
            self._fluent["SimpleCardWidget"]()
            if self._fluent
            else QFrame()
        )
        self.gallery_card.setObjectName("DatasetGalleryCard")
        if not self._fluent:
            self.gallery_card.setFrameShape(QFrame.Shape.StyledPanel)
        gallery_layout = QVBoxLayout(self.gallery_card)
        gallery_layout.setContentsMargins(8, 8, 8, 8)
        gallery_layout.setSpacing(0)

        self.dataset_model = DatasetListModel(self)
        self.grid = DatasetListView()
        self.grid.setObjectName("DatasetGalleryView")
        self.grid.setModel(self.dataset_model)
        gallery_layout.addWidget(self.grid)
        self.dataset_splitter.addWidget(self.gallery_card)

        # The legacy inspector was a tall stack of group boxes. A scroll area
        # keeps every lower action reachable on smaller windows without
        # shrinking the gallery into an unusable size.
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setObjectName("DatasetInspectorScroll")
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.inspector_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.inspector_scroll.setMinimumWidth(340)

        self.inspector = QWidget()
        self.inspector.setObjectName("DatasetInspector")
        inspector_layout = QVBoxLayout(self.inspector)
        inspector_layout.setContentsMargins(4, 0, 4, 0)
        inspector_layout.setSpacing(8)

        self.summary_card = ReviewCard(
            "DatasetSummaryCard",
            fluent=self._fluent,
        )
        # Summary intentionally has no separate title: the compact dataset
        # summary itself is the first hierarchy level.
        self.summary_card.title_label.hide()
        self.stats = self._body_label()
        self.stats.setWordWrap(True)
        self.summary_card.content_layout.addWidget(self.stats)
        inspector_layout.addWidget(self.summary_card)

        self.stat_box = ReviewCard(
            "DatasetStatisticsCard",
            fluent=self._fluent,
        )
        self.stat_content = QWidget()
        self.stat_layout = QGridLayout(self.stat_content)
        self.stat_layout.setContentsMargins(0, 0, 0, 0)
        self.stat_layout.setHorizontalSpacing(6)
        self.stat_layout.setVerticalSpacing(4)
        self.stat_box.content_layout.addWidget(self.stat_content)
        inspector_layout.addWidget(self.stat_box)

        self.analysis_box = ReviewCard(
            "DatasetAnalysisCard",
            fluent=self._fluent,
        )
        self.detail = self._body_label()
        self.detail.setWordWrap(True)
        self.analysis_box.content_layout.addWidget(self.detail)
        inspector_layout.addWidget(self.analysis_box)

        self.manual_box = ReviewCard(
            "DatasetManualStateCard",
            fluent=self._fluent,
        )
        manual_content = QWidget()
        manual_layout = QGridLayout(manual_content)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setHorizontalSpacing(6)
        manual_layout.setVerticalSpacing(6)
        self.manual_status_buttons = []
        for column, value in enumerate(("推荐", "备选", "淘汰")):
            button = self._button()
            if manual_callback is not None:
                button.clicked.connect(
                    lambda _checked=False, v=value: manual_callback(v)
                )
            manual_layout.addWidget(button, 0, column)
            self.manual_status_buttons.append(button)
        self.restore_btn = self._transparent_button()
        if restore_callback is not None:
            self.restore_btn.clicked.connect(restore_callback)
        manual_layout.addWidget(self.restore_btn, 1, 0, 1, 3)
        self.manual_box.content_layout.addWidget(manual_content)
        inspector_layout.addWidget(self.manual_box)

        self.ai_box = ReviewCard(
            "DatasetAIReviewCard",
            fluent=self._fluent,
        )
        self.ai_label = self._body_label()
        self.ai_label.setWordWrap(True)
        self.ai_box.content_layout.addWidget(self.ai_label)
        ai_actions = QHBoxLayout()
        ai_actions.setContentsMargins(0, 0, 0, 0)
        ai_actions.setSpacing(6)
        self.accept_ai_btn = self._button()
        self.reject_ai_btn = self._button()
        self.clear_ai_btn = self._transparent_button()
        if accept_ai_callback is not None:
            self.accept_ai_btn.clicked.connect(accept_ai_callback)
        if reject_ai_callback is not None:
            self.reject_ai_btn.clicked.connect(reject_ai_callback)
        if clear_ai_callback is not None:
            self.clear_ai_btn.clicked.connect(clear_ai_callback)
        ai_actions.addWidget(self.accept_ai_btn)
        ai_actions.addWidget(self.reject_ai_btn)
        ai_actions.addWidget(self.clear_ai_btn)
        ai_actions.addStretch(1)
        self.ai_box.content_layout.addLayout(ai_actions)
        inspector_layout.addWidget(self.ai_box)

        inspector_layout.addStretch(1)
        self.inspector_scroll.setWidget(self.inspector)
        self.dataset_splitter.addWidget(self.inspector_scroll)
        self.dataset_splitter.setStretchFactor(0, 1)
        self.dataset_splitter.setStretchFactor(1, 0)
        self.dataset_splitter.setSizes([1010, 390])
        root.addWidget(self.dataset_splitter, 1)

    @property
    def fluent_enabled(self):
        return self._fluent is not None

    def _button(self):
        return (
            self._fluent["PushButton"]("")
            if self._fluent
            else QPushButton("")
        )

    def _transparent_button(self):
        if self._fluent:
            return self._fluent["TransparentPushButton"]("")
        button = QPushButton("")
        button.setFlat(True)
        return button

    def _body_label(self):
        return (
            self._fluent["BodyLabel"]("")
            if self._fluent
            else QLabel("")
        )

    def make_filter_button(self, text):
        """Create a compact clickable statistic/filter affordance."""
        if self._fluent:
            button = self._fluent["TransparentPushButton"](text)
        else:
            button = QPushButton(text)
            button.setFlat(True)
        return button
