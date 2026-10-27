"""Smoke coverage for portable app settings and shared ORT provider policy."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

settings_spec = importlib.util.spec_from_file_location(
    "face_lora_application_settings",
    SRC / "application" / "settings.py",
)
settings_module = importlib.util.module_from_spec(settings_spec)
sys.modules[settings_spec.name] = settings_module
settings_spec.loader.exec_module(settings_module)
AppSettings = settings_module.AppSettings
SettingsService = settings_module.SettingsService

from infrastructure.inference_runtime import (
    configure_inference_runtime,
    create_ort_session,
    inference_runtime_generation,
    provider_plan,
    runtime_snapshot,
)
from infrastructure.settings_store import JsonSettingsStore


class FakeSession:
    def __init__(self, providers):
        self._providers = list(providers)

    def get_providers(self):
        return list(self._providers)


class FakeOptions:
    def __init__(self):
        self.enable_mem_pattern = True
        self.execution_mode = "parallel"


class FakeExecutionMode:
    ORT_SEQUENTIAL = "sequential"


class FakeOrt:
    available = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    fail_cuda = False
    fail_dml = False
    calls = []
    options_seen = []
    ExecutionMode = FakeExecutionMode

    @classmethod
    def SessionOptions(cls):
        return FakeOptions()

    @classmethod
    def get_available_providers(cls):
        return list(cls.available)

    @classmethod
    def InferenceSession(cls, path, sess_options=None, providers=None, **kwargs):
        cls.calls.append(tuple(providers or ()))
        cls.options_seen.append(sess_options)
        if cls.fail_cuda and providers and providers[0] == "CUDAExecutionProvider":
            raise RuntimeError("synthetic CUDA failure")
        if cls.fail_dml and providers and providers[0] == "DmlExecutionProvider":
            raise RuntimeError("synthetic DirectML failure")
        return FakeSession(providers or ())


with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "_userdata" / "settings.json"
    service = SettingsService(JsonSettingsStore(path))
    assert service.current == AppSettings()

    updated = service.update(
        inference_device="gpu",
        theme="dark",
        background_enrichment=False,
    )
    assert updated.inference_device == "gpu"
    assert updated.theme == "dark"
    assert updated.background_enrichment is False
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["inference_device"] == "gpu"

    path.write_text(
        json.dumps(
            {
                "inference_device": "invalid",
                "theme": "invalid",
                "background_enrichment": True,
            }
        ),
        encoding="utf-8",
    )
    restored = service.reload()
    assert restored.inference_device == "auto"
    assert restored.theme == "system"
    assert restored.background_enrichment is True

configure_inference_runtime("auto")
generation = inference_runtime_generation()
assert configure_inference_runtime("auto") == generation
assert configure_inference_runtime("gpu") == generation + 1

FakeOrt.available = ["CUDAExecutionProvider", "CPUExecutionProvider"]
FakeOrt.fail_cuda = False
FakeOrt.calls = []
plan = provider_plan(FakeOrt)
assert plan.providers == ("CUDAExecutionProvider", "CPUExecutionProvider")
session = create_ort_session(FakeOrt, "model.onnx")
assert session.get_providers()[0] == "CUDAExecutionProvider"

FakeOrt.fail_cuda = True
FakeOrt.calls = []
session = create_ort_session(FakeOrt, "model.onnx")
assert session.get_providers() == ["CPUExecutionProvider"]
assert FakeOrt.calls == [
    ("CUDAExecutionProvider", "CPUExecutionProvider"),
    ("CPUExecutionProvider",),
]
snapshot = runtime_snapshot(FakeOrt)
assert snapshot.last_active_provider == "CPUExecutionProvider"
assert "CPU fallback" in snapshot.fallback_reason

FakeOrt.available = ["DmlExecutionProvider", "CPUExecutionProvider"]
FakeOrt.fail_cuda = False
FakeOrt.fail_dml = False
FakeOrt.calls = []
FakeOrt.options_seen = []
plan = provider_plan(FakeOrt)
assert plan.providers == ("DmlExecutionProvider", "CPUExecutionProvider")
session = create_ort_session(FakeOrt, "model.onnx")
assert session.get_providers()[0] == "DmlExecutionProvider"
dml_options = FakeOrt.options_seen[0]
assert dml_options.enable_mem_pattern is False
assert dml_options.execution_mode == FakeExecutionMode.ORT_SEQUENTIAL

FakeOrt.fail_dml = True
FakeOrt.calls = []
FakeOrt.options_seen = []
session = create_ort_session(FakeOrt, "model.onnx")
assert session.get_providers() == ["CPUExecutionProvider"]
assert FakeOrt.calls == [
    ("DmlExecutionProvider", "CPUExecutionProvider"),
    ("CPUExecutionProvider",),
]
snapshot = runtime_snapshot(FakeOrt)
assert snapshot.last_active_provider == "CPUExecutionProvider"
assert "CPU fallback" in snapshot.fallback_reason

FakeOrt.available = ["CPUExecutionProvider"]
FakeOrt.fail_cuda = False
plan = provider_plan(FakeOrt)
assert plan.providers == ("CPUExecutionProvider",)
assert "unavailable" in plan.fallback_reason

configure_inference_runtime("cpu")
assert provider_plan(FakeOrt).providers == ("CPUExecutionProvider",)

print("Settings + inference runtime smoke OK")
