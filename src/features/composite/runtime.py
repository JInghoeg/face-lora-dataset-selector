"""Minimal DeepGHS YOLO person/head runtime used by Composite Split.

This file vendors and narrows the mature inference path from DeepGHS imgutils
(MIT License, Copyright (c) 2023 DeepGHS), especially:
- imgutils/detect/person.py
- imgutils/detect/head.py
- imgutils/generic/yolo.py
- imgutils/data/encode.py
- imgutils/utils/onnxruntime.py

Only the already-validated person/head ONNX inference path is retained here.
The detector models themselves stay upstream and are downloaded on first use
with SHA-256 verification.

Upstream: https://github.com/deepghs/imgutils
License: MIT
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import onnxruntime as ort

from infrastructure.runtime_tuning import configure_ort_cpu_options
from PIL import Image


@dataclass(frozen=True)
class ModelSpec:
    name: str
    url: str
    sha256: str


PERSON_SPEC = ModelSpec(
    name="person_detect_v1.3_s",
    url=(
        "https://huggingface.co/deepghs/anime_person_detection/resolve/main/"
        "person_detect_v1.3_s/model.onnx?download=true"
    ),
    sha256="6da88929438cd442e31e45ff4f934dd2d7eb9cf7a423c22885d650ee52550f90",
)

HEAD_SPEC = ModelSpec(
    name="head_detect_v2.0_s",
    url=(
        "https://huggingface.co/deepghs/anime_head_detection/resolve/main/"
        "head_detect_v2.0_s/model.onnx?download=true"
    ),
    sha256="6679f9b71192298bbf174d82e9e5581c3237b0c3dc67deace7cdbf686b070a00",
)

_MODEL_DOWNLOAD_LOCK = threading.Lock()
_SESSION_LOCK = threading.Lock()
_SESSIONS = {}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def _ensure_model(spec: ModelSpec, model_cache: Path) -> Path:
    """Download one fixed upstream model into the app-local cache and verify it."""
    folder = model_cache / spec.name
    model = folder / "model.onnx"

    if model.exists() and _sha256_file(model) == spec.sha256:
        return model

    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "model.onnx.part"
    with _MODEL_DOWNLOAD_LOCK:
        if model.exists() and _sha256_file(model) == spec.sha256:
            return model
        if tmp.exists():
            tmp.unlink()

        request = urllib.request.Request(
            spec.url,
            headers={"User-Agent": "Face-LoRA-Dataset-Selector/0.3"},
        )
        h = hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=120) as src, tmp.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    h.update(chunk)
            digest = h.hexdigest().lower()
            if digest != spec.sha256:
                raise RuntimeError(
                    f"{spec.name} 下载校验失败：SHA-256 {digest}，期望 {spec.sha256}"
                )
            tmp.replace(model)
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise
    return model


def _safe_names(names_text: str) -> List[str]:
    value = ast.literal_eval(names_text)
    if not isinstance(value, dict):
        raise RuntimeError("DeepGHS YOLO model metadata names is not a dict.")
    keys = sorted(value)
    if keys != list(range(len(keys))):
        raise RuntimeError(f"Unexpected DeepGHS YOLO class ids: {keys!r}")
    labels = [value[i] for i in keys]
    if any(not isinstance(x, str) for x in labels):
        raise RuntimeError("Unexpected DeepGHS YOLO class label type.")
    return labels


def _session_for(path: Path):
    cache_key = str(path.resolve())
    with _SESSION_LOCK:
        item = _SESSIONS.get(cache_key)
        if item is None:
            options = configure_ort_cpu_options(ort)
            session = ort.InferenceSession(
                cache_key,
                options,
                providers=["CPUExecutionProvider"],
            )
            metadata = session.get_modelmeta().custom_metadata_map
            if "imgsz" in metadata:
                max_infer_size = tuple(json.loads(metadata["imgsz"]))
                if len(max_infer_size) != 2:
                    raise RuntimeError(f"Unexpected model imgsz: {max_infer_size!r}")
            else:
                max_infer_size = 640
            labels = _safe_names(metadata["names"])
            item = (session, max_infer_size, labels, threading.Lock())
            _SESSIONS[cache_key] = item
        return item


def _image_preprocess(
    image: Image.Image,
    max_infer_size: Union[int, Tuple[int, int]] = 1216,
    allow_dynamic: bool = False,
    align: int = 32,
):
    # Kept behavior-compatible with DeepGHS imgutils.generic.yolo.
    if isinstance(max_infer_size, int):
        max_infer_width, max_infer_height = max_infer_size, max_infer_size
    else:
        max_infer_width, max_infer_height = max_infer_size

    old_width, old_height = image.width, image.height
    new_width, new_height = old_width, old_height
    if allow_dynamic:
        ratio = min(max_infer_width / new_width, max_infer_height / new_height)
        if ratio < 1:
            new_width, new_height = new_width * ratio, new_height * ratio
        new_width = int(math.ceil(new_width / align) * align)
        new_height = int(math.ceil(new_height / align) * align)
    else:
        new_width, new_height = max_infer_width, max_infer_height

    new_width, new_height = int(new_width), int(new_height)
    image = image.resize((new_width, new_height))
    return image, (old_width, old_height), (new_width, new_height)


def _rgb_encode(image: Image.Image) -> np.ndarray:
    if image.mode != "RGB":
        image = image.convert("RGB")
    array = np.asarray(image)
    array = np.transpose(array, (2, 0, 1))
    return (array / 255.0).astype(np.float32)


def _xy_postprocess(x, y, old_size, new_size):
    old_width, old_height = old_size
    new_width, new_height = new_size
    x, y = x / new_width * old_width, y / new_height * old_height
    x = int(np.clip(x, a_min=0, a_max=old_width).round())
    y = int(np.clip(y, a_min=0, a_max=old_height).round())
    return x, y


def _xywh2xyxy(x: np.ndarray) -> np.ndarray:
    y = np.copy(x)
    y[..., 0] = x[..., 0] - x[..., 2] / 2
    y[..., 1] = x[..., 1] - x[..., 3] / 2
    y[..., 2] = x[..., 0] + x[..., 2] / 2
    y[..., 3] = x[..., 1] + x[..., 3] / 2
    return y


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        width = np.maximum(0.0, xx2 - xx1 + 1)
        height = np.maximum(0.0, yy2 - yy1 + 1)
        inter = width * height
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return keep


def _end2end_postprocess(output, conf_threshold, iou_threshold, old_size, new_size, labels):
    if output.shape[-1] != 6:
        raise RuntimeError(f"Unexpected end-to-end YOLO output shape: {output.shape!r}")
    selected = output[output[:, 4] > conf_threshold]
    if not selected.size:
        return []
    selected_idx = _nms(selected[:, :4], selected[:, 4], iou_threshold)
    detections = []
    for x0, y0, x1, y1, score, cls in selected[selected_idx]:
        x0, y0 = _xy_postprocess(x0, y0, old_size, new_size)
        x1, y1 = _xy_postprocess(x1, y1, old_size, new_size)
        detections.append(((x0, y0, x1, y1), labels[int(cls.item())], float(score)))
    return detections


def _nms_postprocess(output, conf_threshold, iou_threshold, old_size, new_size, labels):
    if output.shape[0] != 4 + len(labels):
        raise RuntimeError(
            f"Unexpected YOLO output shape {output.shape!r} for labels {labels!r}"
        )

    max_scores = output[4:, :].max(axis=0)
    output = output[:, max_scores > conf_threshold].transpose(1, 0)
    if not output.size:
        return []

    boxes = _xywh2xyxy(output[:, :4])
    scores = output[:, 4:]
    max_scores = scores.max(axis=1)
    indexes = _nms(boxes, max_scores, iou_threshold)
    boxes, scores = boxes[indexes], scores[indexes]

    detections = []
    for box, score in zip(boxes, scores):
        x0, y0 = _xy_postprocess(box[0], box[1], old_size, new_size)
        x1, y1 = _xy_postprocess(box[2], box[3], old_size, new_size)
        class_id = int(score.argmax())
        detections.append(
            ((x0, y0, x1, y1), labels[class_id], float(score[class_id]))
        )
    return detections


def _postprocess(output, conf_threshold, iou_threshold, old_size, new_size, labels):
    if output.shape[-1] == 6:
        return _end2end_postprocess(
            output, conf_threshold, iou_threshold, old_size, new_size, labels
        )
    return _nms_postprocess(
        output, conf_threshold, iou_threshold, old_size, new_size, labels
    )


def _predict(
    image: Image.Image,
    spec: ModelSpec,
    model_cache: Path,
    conf_threshold: float,
    iou_threshold: float,
):
    model_path = _ensure_model(spec, model_cache)
    session, max_infer_size, labels, exec_lock = _session_for(model_path)

    if image.mode != "RGB":
        image = image.convert("RGB")
    new_image, old_size, new_size = _image_preprocess(image, max_infer_size)
    data = _rgb_encode(new_image)[None, ...]

    with exec_lock:
        output, = session.run(["output0"], {"images": data})

    return _postprocess(
        output[0],
        conf_threshold=conf_threshold,
        iou_threshold=iou_threshold,
        old_size=old_size,
        new_size=new_size,
        labels=labels,
    )


def detect_person(
    image: Image.Image,
    model_cache: Path,
    model_name: str = "person_detect_v1.3_s",
    conf_threshold: float = 0.3,
    iou_threshold: float = 0.5,
):
    if model_name != PERSON_SPEC.name:
        raise ValueError(f"Unsupported vendored person model: {model_name!r}")
    return _predict(image, PERSON_SPEC, model_cache, conf_threshold, iou_threshold)


def detect_heads(
    image: Image.Image,
    model_cache: Path,
    model_name: str = "head_detect_v2.0_s",
    conf_threshold: float = 0.4,
    iou_threshold: float = 0.7,
):
    if model_name != HEAD_SPEC.name:
        raise ValueError(f"Unsupported vendored head model: {model_name!r}")
    return _predict(image, HEAD_SPEC, model_cache, conf_threshold, iou_threshold)
