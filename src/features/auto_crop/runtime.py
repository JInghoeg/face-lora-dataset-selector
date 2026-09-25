"""Minimal production ISNetIS ONNX runtime.

Behavior is intentionally kept compatible with the validated DeepGHS imgutils
ISNetIS path:
- RGB float32 [0, 1]
- preserve aspect ratio inside a 1024x1024 zero-padded canvas
- ONNX input name: img
- crop padding back out
- resize mask to source image size

The full dghs-imgutils research dependency is not required at runtime.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

from infrastructure.model_download import ModelSpec, ensure_model
from infrastructure.runtime_tuning import configure_ort_cpu_options


ISNETIS_SPEC = ModelSpec(
    name="skytnt_anime_seg_isnetis",
    filename="isnetis.onnx",
    url=(
        "https://huggingface.co/skytnt/anime-seg/resolve/main/"
        "isnetis.onnx?download=true"
    ),
    sha256="f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99",
)

DEFAULT_SCALE = 1024

_SESSION_LOCK = threading.Lock()
_SESSIONS = {}


def _session_for(model_path: Path):
    key = str(model_path.resolve())
    with _SESSION_LOCK:
        item = _SESSIONS.get(key)
        if item is None:
            options = configure_ort_cpu_options(ort)
            session = ort.InferenceSession(
                key,
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            inputs = session.get_inputs()
            if len(inputs) != 1 or inputs[0].name != "img":
                raise RuntimeError(
                    f"Unexpected ISNetIS input signature: "
                    f"{[(x.name, x.shape) for x in inputs]!r}"
                )
            item = (session, threading.Lock())
            _SESSIONS[key] = item
        return item


def _reuse_roots(model_cache: Path):
    roots = []
    explicit = os.environ.get("FACE_LORA_MODEL_REUSE_ROOTS", "")
    for value in explicit.split(os.pathsep):
        value = value.strip()
        if value:
            roots.append(Path(value))

    # Source/research layout convenience:
    # G:\AI_Research\_FaceLoRA_ModelCache\auto_crop
    # -> G:\AI_Research\_shared_cache\face-lora-dataset-selector
    cache = Path(model_cache).resolve()
    try:
        shared = (
            cache.parent.parent
            / "_shared_cache"
            / "face-lora-dataset-selector"
        )
        roots.append(shared)
    except Exception:
        pass

    # Preserve order while removing duplicates.
    result = []
    seen = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key.casefold() in seen:
            continue
        seen.add(key.casefold())
        result.append(root)
    return result


def get_isnetis_mask(
    image: Image.Image,
    model_cache: Path,
    scale: int = DEFAULT_SCALE,
) -> np.ndarray:
    if image.mode != "RGB":
        image = image.convert("RGB")

    source = np.asarray(image, dtype=np.float32) / 255.0
    h0, w0 = source.shape[:2]
    if h0 <= 0 or w0 <= 0:
        raise ValueError("Empty image.")

    if h0 > w0:
        h = scale
        w = max(1, int(scale * w0 / h0))
    else:
        w = scale
        h = max(1, int(scale * h0 / w0))

    ph, pw = scale - h, scale - w
    canvas = np.zeros((scale, scale, 3), dtype=np.float32)
    resized = cv2.resize(source, (w, h), interpolation=cv2.INTER_LINEAR)
    y0, x0 = ph // 2, pw // 2
    canvas[y0 : y0 + h, x0 : x0 + w] = resized
    tensor = np.transpose(canvas, (2, 0, 1))[None, ...]

    model_path = ensure_model(
        ISNETIS_SPEC,
        Path(model_cache),
        reuse_roots=_reuse_roots(Path(model_cache)),
    )
    session, exec_lock = _session_for(model_path)
    with exec_lock:
        output = session.run(None, {"img": tensor})[0]

    mask = output[0]
    mask = np.transpose(mask, (1, 2, 0))
    mask = mask[y0 : y0 + h, x0 : x0 + w]
    mask = cv2.resize(mask, (w0, h0), interpolation=cv2.INTER_LINEAR)
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    return np.asarray(mask, dtype=np.float32)
