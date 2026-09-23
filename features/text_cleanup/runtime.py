"""Model runtimes owned by the Text Cleanup feature."""
from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from infrastructure.model_download import ModelSpec, ensure_model


MIGAN_SPEC = ModelSpec(
    name="migan",
    filename="migan_pipeline_v2.onnx",
    url=(
        "https://huggingface.co/andraniksargsyan/migan/resolve/"
        "1538c135034b8cfe7a8472f34d09c8a5a45b17a7/"
        "migan_pipeline_v2.onnx?download=true"
    ),
    sha256="6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b",
)

_SESSION_LOCK = threading.Lock()
_SESSIONS = {}


def model_exists(cache_root: Path, reuse_roots=()):
    target = Path(cache_root) / MIGAN_SPEC.name / MIGAN_SPEC.filename
    if target.exists():
        return True
    for root in reuse_roots:
        root = Path(root)
        if not root.exists():
            continue
        try:
            if any(root.rglob(MIGAN_SPEC.filename)):
                return True
        except OSError:
            continue
    return False


def ensure_migan(cache_root: Path, reuse_roots=()) -> Path:
    return ensure_model(
        MIGAN_SPEC,
        Path(cache_root),
        reuse_roots=tuple(Path(x) for x in reuse_roots),
    )


class MIRepair:
    """Official MI-GAN ONNX pipeline used by the existing text-cleanup UI."""

    def __init__(self, model_path: Path):
        key = str(Path(model_path).resolve())
        with _SESSION_LOCK:
            session = _SESSIONS.get(key)
            if session is None:
                session = ort.InferenceSession(
                    key,
                    providers=["CPUExecutionProvider"],
                )
                _SESSIONS[key] = session
        self.session = session

    def run(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        joined = cv2.dilate(
            mask,
            cv2.getStructuringElement(cv2.MORPH_RECT, (25, 13)),
        )
        contours, _ = cv2.findContours(
            joined,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        result = image.copy()
        h, w = mask.shape

        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            pad = max(48, int(max(bw, bh) * .55))
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(w, x + bw + pad)
            y1 = min(h, y + bh + pad)

            local_mask = mask[y0:y1, x0:x1]
            if not np.any(local_mask):
                continue

            rgb = cv2.cvtColor(
                image[y0:y1, x0:x1],
                cv2.COLOR_BGR2RGB,
            )
            known = 255 - local_mask
            feeds = {
                "image": np.ascontiguousarray(
                    rgb.transpose(2, 0, 1)[None]
                ),
                "mask": np.ascontiguousarray(
                    known[None, None]
                ),
            }
            output = self.session.run(None, feeds)[0][0]
            if output.shape[0] == 3:
                output = output.transpose(1, 2, 0)
            fixed = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
            area = result[y0:y1, x0:x1]
            area[local_mask > 0] = fixed[local_mask > 0]

        return result
