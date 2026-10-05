"""Regression contract for the v0.3.1 stability baseline carried into v0.4."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


app = text("src/app_main.py")
selector = text("src/application/selector.py")
runtime_log = text("src/infrastructure/runtime_log.py")
spec = text("packaging/portable.spec")
build = text("tools/build_portable.ps1")

# Native-crash regression: worker signals that reach QWidget state must have a
# QObject receiver and explicit queued delivery.
assert "Signal, Slot," in app
for risky in (
    "self.worker.status.connect(lambda",
    "self.worker.progress.connect(lambda",
    "self.worker.failed.connect(lambda",
    "self.worker.cancelled.connect(lambda",
    "self.auto_crop_worker.progress.connect(lambda",
    "self.auto_crop_worker.cancelled.connect(lambda",
    "self.composite_worker.progress.connect(lambda",
    "self.composite_worker.cancelled.connect(lambda",
    "self.incremental_worker.progress.connect(lambda",
    "self.incremental_worker.cancelled.connect(lambda",
    "self.organizer_worker.progress.connect(lambda",
    "thread.finished.connect(lambda t=thread:self.thumbnail_thread_done(t))",
):
    assert risky not in app, risky

for expected in (
    "self.worker.status.connect(self.dataset_status,Qt.ConnectionType.QueuedConnection)",
    "self.worker.progress.connect(self.dataset_progress,Qt.ConnectionType.QueuedConnection)",
    "self.worker.failed.connect(self.dataset_failed,Qt.ConnectionType.QueuedConnection)",
    "self.auto_crop_worker.progress.connect(self.auto_crop_progress,Qt.ConnectionType.QueuedConnection)",
    "self.composite_worker.progress.connect(self.composite_progress,Qt.ConnectionType.QueuedConnection)",
    "self.incremental_worker.progress.connect(self.incremental_progress,Qt.ConnectionType.QueuedConnection)",
    "self.organizer_worker.progress.connect(self.organizer_progress,Qt.ConnectionType.QueuedConnection)",
    "self.export_worker.progress.connect(self.export_progress, Qt.ConnectionType.QueuedConnection)",
    "thread.finished.connect(self.thumbnail_thread_finished)",
):
    assert expected in app, expected

# Portable persistence regression: normal application-controlled state is local.
assert 'self.model_cache_root = app_root / "_FaceLoRA_ModelCache"' in selector
assert 'user_data_root = app_root / "_userdata"' in selector
assert 'self.bundled_models_root = resource_root / "models"' in selector
assert 'return base / "logs"' in runtime_log
assert "LOCALAPPDATA" not in runtime_log

# Portable completeness regression: all redistributable runtime weights must be
# present in the spec and verified by the build.
for model_path in (
    "resources/models/composite_split_cache/person_detect_v1.3_s/model.onnx",
    "resources/models/composite_split_cache/head_detect_v2.0_s/model.onnx",
    "resources/models/auto_crop/skytnt_anime_seg_isnetis/isnetis.onnx",
    "resources/models/text_cleanup/migan/migan_pipeline_v2.onnx",
):
    assert model_path in spec, model_path

assert "tools/prepare_bundled_models.py --root resources/models" in build
assert 'tools/prepare_bundled_models.py --root (Join-Path $portable "_internal\\models") --verify-only' in build

print("v0.3.1 -> v0.4 carry-forward contract OK")
