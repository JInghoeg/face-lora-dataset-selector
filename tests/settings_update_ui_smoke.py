"""Qt Settings screen: update must not auto-download or install when auto-check is enabled."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

FILE = Path(__file__).resolve().parents[1] / "src" / "ui" / "qt" / "settings_page.py"
spec = importlib.util.spec_from_file_location("settings_page_ui_under_test", FILE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test():
    app = QApplication.instance() or QApplication([])
    page = module.SettingsPage(
        auto_check=True, version="v0.4.0",
        inference_device="gpu", background_enrichment=False, theme="dark",
    )
    page.resize(900, 650)
    page.show()
    app.processEvents()
    signals = []
    page.updates.check_requested.connect(lambda: signals.append("check"))
    page.updates.install_requested.connect(lambda: signals.append("install"))
    page.updates.auto_check_changed.connect(lambda value: signals.append(f"auto:{value}"))
    assert page.updates.auto_check.isChecked()
    assert not page.updates.install_button.isEnabled()
    assert page.navigation.count() == 3
    assert page.device_combo.currentData() == "gpu"
    assert not page.background_check.isChecked()
    assert page.theme_combo.currentData() == "dark"
    settings_events = []
    page.inference_device_changed.connect(lambda mode: settings_events.append(("device",mode)))
    page.background_enrichment_changed.connect(lambda enabled: settings_events.append(("scan",enabled)))
    page.theme_changed.connect(lambda value: settings_events.append(("theme",value)))
    page.navigation.setCurrentRow(1)
    assert page.pages.currentIndex() == 1
    page.device_combo.setCurrentIndex(page.device_combo.findData("cpu"))
    page.background_check.setChecked(True)
    page.navigation.setCurrentRow(0)
    page.theme_combo.setCurrentIndex(page.theme_combo.findData("system"))
    assert settings_events == [
        ("device", "cpu"), ("scan", True), ("theme", "system")
    ], settings_events
    page.set_preferences(
        inference_device="auto", background_enrichment=False, theme="light"
    )
    assert page.device_combo.currentData() == "auto"
    assert page.theme_combo.currentData() == "light"
    assert not page.background_check.isChecked()
    assert len(settings_events) == 3, "Programmatic load reconfigured runtime"
    page.show_updates()
    assert page.pages.currentIndex() == 2
    # Initial check is not a download permission.
    page.updates.check_button.click()
    assert signals == ["check"], signals
    page.updates.set_status("available", latest="v0.4.1", download_bytes=35_000_000)
    app.processEvents()
    assert page.updates.install_button.isEnabled()
    assert "v0.4.1" in page.updates.info_label.text()
    assert "MiB" in page.updates.info_label.text()
    assert signals == ["check"]
    # Only an explicit click may raise the install request.
    page.updates.install_button.click()
    assert signals == ["check", "install"]
    page.updates.set_status("downloading")
    assert not page.updates.install_button.isEnabled()
    assert not page.updates.check_button.isEnabled()
    page.updates.set_status("no_delta",latest="v0.4.2")
    assert not page.updates.install_button.isEnabled()
    assert page.updates.check_button.isEnabled()
    page.updates.auto_check.setChecked(False)
    assert signals[-1] == "auto:False"
    page.close()
    app.processEvents()
    print("Settings: appearance, inference, background scan and explicit delta update PASS")


if __name__ == "__main__":
    test()
