"""Settings screen presentation: update controls are NOT a standalone app module.

This widget owns layout/signals only. Stable release detection, SHA validation,
delta downloading, and installation are delegated to the application layer.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)


def _tr(source: str) -> str:
    return QCoreApplication.translate("SettingsPage", source)


class SoftwareUpdateSection(QFrame):
    check_requested = Signal()
    install_requested = Signal()
    auto_check_changed = Signal(bool)

    def __init__(self, auto_check: bool, version: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SoftwareUpdateSection")
        self.setStyleSheet(
            "QFrame#SoftwareUpdateSection { border:1px solid #c6cad2;"
            " border-radius:10px; }"
        )
        self.version = version
        self.latest = ""
        self.download_bytes = None
        self._available = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 15, 18, 18)
        outer.setSpacing(12)
        self.title = QLabel()
        self.title.setStyleSheet("font-size:16px;font-weight:600;border:none")
        outer.addWidget(self.title)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setStyleSheet("border:none")
        outer.addWidget(self.description)
        self.version_label = QLabel()
        self.version_label.setStyleSheet("font-size:13px;border:none")
        outer.addWidget(self.version_label)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("border:none;color:#667085")
        outer.addWidget(self.info_label)
        self.auto_check = QCheckBox()
        self.auto_check.setChecked(bool(auto_check))
        self.auto_check.toggled.connect(self.auto_check_changed.emit)
        outer.addWidget(self.auto_check)
        actions = QHBoxLayout()
        self.check_button = QPushButton()
        self.check_button.setMinimumHeight(34)
        self.check_button.clicked.connect(lambda _checked=False: self.check_requested.emit())
        actions.addWidget(self.check_button)
        self.install_button = QPushButton()
        self.install_button.setObjectName("StableUpdateAction")
        self.install_button.setMinimumHeight(34)
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(lambda _checked=False: self.install_requested.emit())
        actions.addWidget(self.install_button)
        actions.addStretch()
        outer.addLayout(actions)
        self.state = "unchecked"
        self.retranslate()

    def retranslate(self):
        self.title.setText(_tr("软件更新"))
        self.description.setText(_tr("自动检查正式稳定版；仅在点击按钮后下载并安装增量更新。"))
        self.auto_check.setText(_tr("自动检查稳定版更新"))
        self.check_button.setText(_tr("检查更新"))
        self.install_button.setText(_tr("一键增量更新并重启"))
        self._update_view()

    @staticmethod
    def _size(n):
        if n is None:
            return ""
        amount = float(n) / 1024 / 1024
        return f"{amount:.1f} MiB"

    def set_status(self, state: str, *, latest: str = "",
                   download_bytes=None, detail: str = ""):
        self.state = state
        if latest:
            self.latest = latest
        self.download_bytes = download_bytes
        self.detail = detail
        self._available = state == "available"
        self._update_view()

    def _update_view(self):
        self.version_label.setText(
            _tr("当前版本：{version}").format(version=self.version)
        )
        text = {
            "unchecked": _tr("尚未检查更新"),
            "checking": _tr("正在检查最新稳定版…"),
            "downloading": _tr("正在下载并校验增量包…"),
            "available": _tr("发现最新稳定版：{version}").format(
                version=self.latest
            ),
            "no_delta": _tr("发现稳定版 {version}，但没有兼容的增量包；不会下载完整包").format(
                version=self.latest
            ),
            "current": _tr("已是最新稳定版"),
            "development": _tr("开发测试版不参与稳定版自动更新"),
            "prepared": _tr("更新已准备好，等待安全退出并安装"),
            "error": _tr("检查更新失败：{reason}").format(
                reason=getattr(self, "detail", "")
            ),
            "not_due": _tr("已按自动检查间隔跳过重复检查"),
        }.get(self.state, _tr("尚未检查更新"))
        if self.state == "available" and self.download_bytes is not None:
            text += " · " + _tr("需要下载 {size}").format(
                size=self._size(self.download_bytes)
            )
        self.info_label.setText(text)
        self.check_button.setEnabled(self.state not in ("checking", "downloading", "prepared"))
        self.install_button.setEnabled(self._available)


class _SettingsGroup(QFrame):
    """Reusable section with compact, horizontally aligned setting rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsSection")
        self.setStyleSheet(
            "QFrame#SettingsSection { border:1px solid palette(mid); "
            "border-radius:10px; } "
            "QFrame#SettingsSection QLabel { border: none; }"
        )
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(18, 16, 18, 17)
        self.content.setSpacing(13)
        self.heading = QLabel()
        self.heading.setStyleSheet("font-size:16px;font-weight:600")
        self.content.addWidget(self.heading)

    def add_setting(self, label: QLabel, description: QLabel, widget: QWidget):
        row = QHBoxLayout()
        row.setSpacing(18)
        stack = QVBoxLayout()
        stack.setSpacing(3)
        stack.addWidget(label)
        description.setWordWrap(True)
        description.setStyleSheet("color: palette(mid)")
        stack.addWidget(description)
        row.addLayout(stack, 1)
        row.addWidget(widget, 0, Qt.AlignVCenter)
        self.content.addLayout(row)
        return row


class SettingsPage(QWidget):
    """A single persistent Settings tab; each group remains feature-owned.

    Settings are dispatched as values to the application layer. No ONNX runtime
    or dataset processing code lives in this Qt presentation component.
    """

    inference_device_changed = Signal(str)
    background_enrichment_changed = Signal(bool)
    theme_changed = Signal(str)

    def __init__(
        self, auto_check: bool, version: str, parent=None,
        *, inference_device: str = "auto",
        background_enrichment: bool = True, theme: str = "system",
    ):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.setMinimumWidth(600)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 18, 16)
        outer.setSpacing(18)
        self.navigation = QListWidget()
        self.navigation.setObjectName("SettingsNavigation")
        self.navigation.setFixedWidth(172)
        self.navigation.setSpacing(3)
        self.navigation.addItems(["", "", ""])
        self.navigation.setStyleSheet(
            "QListWidget#SettingsNavigation { border: none; "
            "background: transparent; outline: none; } "
            "QListWidget#SettingsNavigation::item {"
            "padding:10px 12px; border-radius:7px; } "
            "QListWidget#SettingsNavigation::item:selected {"
            "background:palette(highlight); color:palette(highlighted-text); }"
        )
        outer.addWidget(self.navigation)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)

        self.general, general_content = self._page()
        self.compute, compute_content = self._page()
        self.updates_page, updates_content = self._page()

        self.general_group = _SettingsGroup()
        self.theme_label = QLabel()
        self.theme_description = QLabel()
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("SettingsTheme")
        self.theme_combo.setMinimumWidth(165)
        for mode in ("system", "light", "dark"):
            self.theme_combo.addItem("", mode)
        self.general_group.add_setting(
            self.theme_label, self.theme_description, self.theme_combo
        )
        general_content.addWidget(self.general_group)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)

        self.compute_group = _SettingsGroup()
        self.device_label = QLabel()
        self.device_description = QLabel()
        self.device_combo = QComboBox()
        self.device_combo.setObjectName("SettingsInferenceDevice")
        self.device_combo.setMinimumWidth(165)
        for value in ("auto", "gpu", "cpu"):
            self.device_combo.addItem("", value)
        self.compute_group.add_setting(
            self.device_label, self.device_description, self.device_combo
        )
        self.compute_group.content.addSpacing(6)
        self.background_label = QLabel()
        self.background_description = QLabel()
        self.background_check = QCheckBox()
        self.background_check.setObjectName("SettingsBackgroundScan")
        self.background_check.setMinimumWidth(60)
        self.compute_group.add_setting(
            self.background_label, self.background_description, self.background_check
        )
        compute_content.addWidget(self.compute_group)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.background_check.toggled.connect(self.background_enrichment_changed.emit)

        self.updates = SoftwareUpdateSection(auto_check, version)
        updates_content.addWidget(self.updates)

        self.set_preferences(
            inference_device=inference_device,
            background_enrichment=background_enrichment,
            theme=theme,
        )
        self.navigation.setCurrentRow(0)
        self.retranslate()

    def _page(self):
        """Give each settings category its own scroll view and section stack."""
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(8, 9, 14, 16)
        content.setSpacing(14)
        heading = QLabel()
        heading.setObjectName("SettingsPageHeading")
        heading.setStyleSheet("font-size:21px;font-weight:600")
        content.addWidget(heading)
        content.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.pages.addWidget(host)
        if not hasattr(self, "_page_headers"):
            self._page_headers = []
        self._page_headers.append(heading)
        return host, content

    @staticmethod
    def _combo_value(combo):
        return str(combo.currentData())

    def _on_device_changed(self, _index):
        self.inference_device_changed.emit(self._combo_value(self.device_combo))

    def _on_theme_changed(self, _index):
        self.theme_changed.emit(self._combo_value(self.theme_combo))

    def set_preferences(self, *, inference_device, background_enrichment, theme):
        # Programmatic settings reload must not spuriously reconfigure ONNX.
        for combo, value in (
            (self.device_combo, inference_device),
            (self.theme_combo, theme),
        ):
            combo.blockSignals(True)
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)
        self.background_check.blockSignals(True)
        self.background_check.setChecked(bool(background_enrichment))
        self.background_check.blockSignals(False)

    def show_updates(self):
        self.navigation.setCurrentRow(2)
        self.updates.setFocus()

    def retranslate(self):
        labels = (
            _tr("常规"), _tr("性能与分析"), _tr("软件更新")
        )
        for index, label in enumerate(labels):
            self.navigation.item(index).setText(label)
            self._page_headers[index].setText(label)
        self.general_group.heading.setText(_tr("外观"))
        self.theme_label.setText(_tr("复核窗口主题"))
        self.theme_description.setText(
            _tr("同步新式复核窗口的默认外观；主界面视觉统一仍在逐模块推进。")
        )
        for i, label in enumerate(("跟随系统", "浅色", "深色")):
            self.theme_combo.setItemText(i, _tr(label))
        self.compute_group.heading.setText(_tr("模型运行"))
        self.device_label.setText(_tr("推理设备"))
        self.device_description.setText(
            _tr("自动优先可用 GPU；GPU 模式允许 CPU 回退。修改后仅影响新建推理会话。")
        )
        for i, label in enumerate(("自动", "优先 GPU", "仅 CPU")):
            self.device_combo.setItemText(i, _tr(label))
        self.background_label.setText(_tr("后台预扫描"))
        self.background_description.setText(
            _tr("完成数据集分析后，自动预扫描组合图拆分和裁剪候选；关闭不影响手动复核。")
        )
        self.updates.retranslate()
