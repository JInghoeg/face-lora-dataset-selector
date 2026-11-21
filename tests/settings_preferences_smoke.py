"""Settings persistence regression: update status stays separate from dataset cache."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import json

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src" / "application" / "settings.py"
spec = importlib.util.spec_from_file_location("app_settings_under_test", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FileStore:
    def __init__(self, path):
        self.path = path

    def load(self):
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, value):
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test():
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "_userdata" / "settings.json"
        target.parent.mkdir()
        target.write_text(
            '{"inference_device":"gpu","theme":"dark","background_enrichment":false,'
            '"stable_auto_update":false}',
            encoding="utf-8",
        )
        service = module.SettingsService(FileStore(target))
        old = service.current
        assert old.inference_device == "gpu"
        assert old.theme == "dark"
        assert old.background_enrichment is False
        assert old.stable_auto_check is False, "Existing explicit preference lost"
        updated = service.update(
            inference_device="cpu", theme="system",
            background_enrichment=True, stable_auto_check=True,
        )
        assert updated.inference_device == "cpu"
        assert updated.theme == "system"
        assert updated.background_enrichment
        assert updated.stable_auto_check
        assert "stable_auto_update" not in json.loads(target.read_text())
        reloaded = module.SettingsService(FileStore(target)).current
        assert reloaded == updated, "Settings did not persist across restart"
        # Invalid provider/theme values normalize; no dataset files are created.
        invalid = module.AppSettings.from_dict({"inference_device":"invalid","theme":"invalid"})
        assert invalid.inference_device == "auto"
        assert invalid.theme == "system"
        assert list(Path(directory).rglob("*")) == [
            target.parent,
            target,
        ], "Settings created unexpected dataset/cache directories"
        print("Settings persistence, old auto-update preference migration, provider normalization: PASS")


if __name__ == "__main__":
    test()
