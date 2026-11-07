"""Settings screen presentation: update controls are NOT a standalone app module.

This widget owns layout/signals only. Stable release detection, SHA validation,
delta downloading, and installation are delegated to the application layer.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
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
        self.check_button.clicked.connect(self.check_requested.emit)
        actions.addWidget(self.check_button)
        self.install_button = QPushButton()
        self.install_button.setObjectName("StableUpdateAction")
        self.install_button.setMinimumHeight(34)
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install_requested.emit)
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


class SettingsPage(QWidget):
    """The normal Settings tab, with a dedicated Software Updates section."""

    def __init__(self, auto_check: bool, version: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(12, 10, 12, 16)
        content.setSpacing(16)
        self.heading = QLabel()
        self.heading.setStyleSheet("font-size:21px;font-weight:600;")
        content.addWidget(self.heading)
        self.updates = SoftwareUpdateSection(auto_check, version)
        content.addWidget(self.updates)
        content.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.retranslate()

    def retranslate(self):
        self.heading.setText(_tr("设置"))
        self.updates.retranslate()
