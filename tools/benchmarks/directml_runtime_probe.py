#!/usr/bin/env python
"""CI research probe for the optional DirectML runtime profile.

This probe never changes the universal CPU profile. It verifies that the
DirectML distribution exposes the expected provider and that real project ONNX
models can be opened through the shared provider policy with mandatory CPU
fallback.
"""
from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import onnxruntime as ort

from infrastructure.inference_runtime import (
    configure_inference_runtime,
    create_ort_session,
    provider_plan,
    runtime_snapshot,
)
from infrastructure.runtime_tuning import configure_ort_cpu_options


MODEL_PATHS = (
    "resources/models/ediffiqa_t.onnx",
    "resources/models/mb1_120x120.onnx",
    "resources/models/ppocrv5_mobile_det/inference.onnx",
    "resources/models/composite_split_cache/person_detect_v1.3_s/model.onnx",
    "resources/models/composite_split_cache/head_detect_v2.0_s/model.onnx",
    "resources/models/auto_crop/skytnt_anime_seg_isnetis/isnetis.onnx",
    "resources/models/text_cleanup/migan/migan_pipeline_v2.onnx",
)


def _distribution_size(name: str) -> int:
    dist = metadata.distribution(name)
    total = 0
    for item in dist.files or ():
        try:
            path = Path(dist.locate_file(item))
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def main() -> int:
    configure_inference_runtime("gpu")
    available = tuple(ort.get_available_providers())
    plan = provider_plan(ort, "gpu")

    report = {
        "python": sys.version,
        "onnxruntime_version": ort.__version__,
        "distribution": {
            "name": "onnxruntime-directml",
            "version": metadata.version("onnxruntime-directml"),
            "installed_bytes": _distribution_size("onnxruntime-directml"),
        },
        "available_providers": available,
        "provider_plan": plan.providers,
        "models": [],
    }

    if "DmlExecutionProvider" not in available:
        raise RuntimeError(
            "onnxruntime-directml installed without DmlExecutionProvider"
        )
    if "CPUExecutionProvider" not in available:
        raise RuntimeError("DirectML profile has no CPU fallback provider")
    if plan.providers[:2] != (
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    ):
        raise RuntimeError(f"unexpected DirectML provider plan: {plan.providers!r}")

    for relative in MODEL_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)

        options = configure_ort_cpu_options(ort)
        session = create_ort_session(
            ort,
            path,
            sess_options=options,
            preference="gpu",
        )
        active = tuple(session.get_providers())
        snapshot = runtime_snapshot(ort)
        report["models"].append(
            {
                "path": relative,
                "providers": active,
                "fallback_reason": snapshot.fallback_reason,
                "inputs": [
                    {
                        "name": value.name,
                        "shape": value.shape,
                        "type": value.type,
                    }
                    for value in session.get_inputs()
                ],
            }
        )

    output = ROOT / "_research_output" / "directml-runtime.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"Wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
