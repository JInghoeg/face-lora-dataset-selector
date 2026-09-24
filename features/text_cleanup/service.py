"""Subtitle / watermark detection and repair backend.

Detection and repair deliberately remain one feature. This module preserves the
existing PP-OCR suggestion heuristics and repair behavior while removing model,
cache and filesystem work from the Qt presentation layer.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import cv2
import numpy as np

from core.cancellation import check_cancelled
from core.models import TextPhoto
from infrastructure.filesystem import IMAGE_EXTENSIONS
from .detector import TextDetector
from .runtime import MIRepair, ensure_migan, model_exists


AI_METHOD = "AI 修复（MI-GAN）"
TELEA_METHOD = "快速修复（TELEA）"
NS_METHOD = "Navier-Stokes"
METHODS = (AI_METHOD, TELEA_METHOD, NS_METHOD)
STATE_VERSION = 2


@dataclass
class TextCleanupState:
    folder: Optional[Path] = None
    output: Optional[Path] = None
    method: str = AI_METHOD
    expand: int = 5
    radius: int = 4
    min_height: int = 6
    min_area: int = 36
    min_conf: float = 0.0
    records: list[TextPhoto] = field(default_factory=list)


@dataclass
class TextCleanupBatchResult:
    written: int = 0


def _key(path: Path) -> str:
    return str(Path(path).resolve()).casefold()


def detector_config(model_path: Path):
    return {
        "model_path": str(model_path),
        "limit_side_len": 960,
        "limit_type": "min",
        "mean": [.485, .456, .406],
        "std": [.229, .224, .225],
        "thresh": .3,
        "box_thresh": .6,
        "max_candidates": 1000,
        "unclip_ratio": 1.5,
        "use_dilation": False,
        "score_mode": "fast",
        "use_cuda": False,
        "use_dml": False,
        "intra_op_num_threads": -1,
        "inter_op_num_threads": -1,
    }


def _detected(detector: TextDetector, image: np.ndarray):
    shape = image.shape[:2]
    detector.preprocess_op = detector.get_preprocess(max(shape))
    tensor = detector.preprocess_op(image)
    if tensor is None:
        return [], []

    boxes, scores = detector.postprocess_op(
        detector.infer(tensor)[0],
        shape,
    )
    boxes = detector.filter_tag_det_res(boxes, shape)
    boxes = (
        np.asarray(boxes).astype(int).tolist()
        if len(boxes)
        else []
    )
    scores = [
        float(value)
        for value in np.asarray(scores).reshape(-1)
    ]
    if len(scores) != len(boxes):
        scores = [1.0] * len(boxes)
    return boxes, scores


def source_name(path: Path):
    path = Path(path)
    if "_frame_" in path.stem:
        return path.stem.split("_frame_", 1)[0]
    return str(path.parent.resolve())


def suggest(records, targets=None):
    """Preserve the existing conservative subtitle/overlay suggestion rule."""
    repeats = defaultdict(int)

    for record in (targets or records):
        try:
            image = cv2.imdecode(
                np.fromfile(str(record.path), np.uint8),
                cv2.IMREAD_GRAYSCALE,
            )
            h, w = image.shape[:2]
            for box in record.boxes:
                arr = np.asarray(box)
                repeats[
                    (
                        source_name(record.path),
                        round(float(arr[:, 0].mean()) / w, 1),
                        round(float(arr[:, 1].mean()) / h, 1),
                    )
                ] += 1
        except Exception:
            pass

    for record in records:
        try:
            image = cv2.imdecode(
                np.fromfile(str(record.path), np.uint8),
                cv2.IMREAD_GRAYSCALE,
            )
            h, w = image.shape[:2]
            values = []

            for box in record.boxes:
                arr = np.asarray(box)
                bw = max(1, arr[:, 0].max() - arr[:, 0].min())
                bh = max(1, arr[:, 1].max() - arr[:, 1].min())
                cx = float(arr[:, 0].mean()) / w
                cy = float(arr[:, 1].mean()) / h
                edge = cy < .18 or cy > .70
                line = bw / w >= .12 and bw / bh >= 1.35
                repeated = repeats[
                    (
                        source_name(record.path),
                        round(cx, 1),
                        round(cy, 1),
                    )
                ] >= 2
                values.append(
                    bool(
                        (edge and line)
                        or (repeated and edge and bw / w >= .06)
                    )
                )

            record.suggested = values
            record.selected = list(values)
            record.manual = [False] * len(values)
        except Exception:
            record.suggested = [False] * len(record.boxes)
            record.selected = [False] * len(record.boxes)
            record.manual = [False] * len(record.boxes)


class TextCleanupService:
    def __init__(
        self,
        *,
        ocr_model_path: Path,
        state_path: Path,
        model_cache: Path,
        model_reuse_roots=(),
    ):
        self.ocr_model_path = Path(ocr_model_path)
        self.state_path = Path(state_path)
        self.model_cache = Path(model_cache)
        self.model_reuse_roots = tuple(
            Path(x) for x in model_reuse_roots
        )
        self._repair_model = None

    def _raw_state(self):
        try:
            return json.loads(
                self.state_path.read_text(encoding="utf-8")
            )
        except Exception:
            return {}

    def detector_smoke_test(self):
        if not self.ocr_model_path.exists():
            raise RuntimeError(
                f"缺少文字检测模型：{self.ocr_model_path}"
            )
        detector = TextDetector(
            detector_config(self.ocr_model_path)
        )
        image = np.full((640, 640, 3), 255, dtype=np.uint8)
        cv2.putText(
            image,
            "TEST 123",
            (70, 350),
            cv2.FONT_HERSHEY_SIMPLEX,
            3.0,
            (0, 0, 0),
            8,
            cv2.LINE_AA,
        )
        boxes, _ = _detected(detector, image)
        if not boxes:
            raise RuntimeError(
                "PP-OCR text detector self-test found no text"
            )
        return len(boxes)

    def state_records(self, folder: Path):
        data = self._raw_state()
        if (
            not folder
            or str(data.get("folder", "")).casefold()
            != _key(folder)
        ):
            return {}
        return {
            str(item.get("path", "")).casefold(): item
            for item in data.get("records", [])
            if isinstance(item, dict)
        }

    def load_state(self) -> TextCleanupState:
        data = self._raw_state()
        folder_raw = data.get("folder")
        output_raw = data.get("output")
        folder = (
            Path(folder_raw)
            if folder_raw and Path(folder_raw).exists()
            else None
        )
        output = Path(output_raw) if output_raw else None

        filters = data.get("filters", {})
        state = TextCleanupState(
            folder=folder,
            output=output,
            method=(
                data.get("method")
                if data.get("method") in METHODS
                else AI_METHOD
            ),
            expand=int(data.get("expand", 5)),
            radius=int(data.get("radius", 4)),
            min_height=int(filters.get("min_height", 6)),
            min_area=int(filters.get("min_area", 36)),
            min_conf=float(filters.get("min_conf", 0.0)),
        )

        restored = []
        for item in data.get("records", []):
            if not isinstance(item, dict):
                continue
            path = Path(item.get("path", ""))
            if not path.exists():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if (
                stat.st_size != item.get("file_size")
                or stat.st_mtime_ns != item.get("mtime_ns")
            ):
                continue

            boxes = list(item.get("boxes", []))
            selected = (
                list(item.get("selected", []))
                + [False] * len(boxes)
            )[:len(boxes)]
            manual = (
                list(item.get("manual", []))
                + [False] * len(boxes)
            )[:len(boxes)]
            scores = (
                list(item.get("scores", []))
                + [1.0] * len(boxes)
            )[:len(boxes)]
            suggested = (
                list(item.get("suggested", selected))
                + [False] * len(boxes)
            )[:len(boxes)]

            restored.append(
                TextPhoto(
                    path,
                    stat.st_size,
                    stat.st_mtime_ns,
                    boxes,
                    selected,
                    manual,
                    scores,
                    suggested,
                    int(item.get("width", 0)),
                    int(item.get("height", 0)),
                )
            )

        state.records = restored
        return state

    def save_state(
        self,
        *,
        folder,
        output,
        records,
        method,
        expand,
        radius,
        min_height,
        min_area,
        min_conf,
    ):
        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        payload = {
            "version": STATE_VERSION,
            "folder": _key(folder) if folder else "",
            "output": str(output) if output else "",
            "method": method if method in METHODS else AI_METHOD,
            "expand": int(expand),
            "radius": int(radius),
            "filters": {
                "min_height": int(min_height),
                "min_area": int(min_area),
                "min_conf": float(min_conf),
            },
            "records": [
                {
                    "path": _key(record.path),
                    "file_size": record.file_size,
                    "mtime_ns": record.mtime_ns,
                    "boxes": record.boxes,
                    "selected": record.selected,
                    "manual": record.manual,
                    "scores": record.scores,
                    "suggested": record.suggested,
                    "width": record.width,
                    "height": record.height,
                }
                for record in records
            ],
        }
        self.state_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    def scan_folder(
        self,
        folder: Path,
        cached=None,
        progress=None,
        cancelled=None,
    ):
        folder = Path(folder)
        cached = cached or {}
        progress = progress or (
            lambda _current, _total, _name: None
        )

        files = sorted(
            (
                path
                for path in folder.rglob("*")
                if path.is_file()
                and path.suffix.lower() in IMAGE_EXTENSIONS
            ),
            key=lambda path: str(path).lower(),
        )

        detector = None
        output = []
        fresh = []

        for index, path in enumerate(files, 1):
            check_cancelled(cancelled)
            stat = path.stat()
            old = cached.get(_key(path))

            if (
                old
                and old.get("file_size") == stat.st_size
                and old.get("mtime_ns") == stat.st_mtime_ns
            ):
                boxes = list(old.get("boxes", []))
                selected = (
                    list(old.get("selected", []))
                    + [False] * len(boxes)
                )[:len(boxes)]
                manual = (
                    list(
                        old.get(
                            "manual",
                            [False] * len(boxes),
                        )
                    )
                    + [False] * len(boxes)
                )[:len(boxes)]
                scores = (
                    list(old.get("scores", [1.0] * len(boxes)))
                    + [1.0] * len(boxes)
                )[:len(boxes)]
                suggested = (
                    list(old.get("suggested", selected))
                    + [False] * len(boxes)
                )[:len(boxes)]

                output.append(
                    TextPhoto(
                        path,
                        stat.st_size,
                        stat.st_mtime_ns,
                        boxes,
                        selected,
                        manual,
                        scores,
                        suggested,
                        int(old.get("width", 0)),
                        int(old.get("height", 0)),
                    )
                )
            else:
                if not self.ocr_model_path.exists():
                    raise RuntimeError(
                        f"缺少文字检测模型：{self.ocr_model_path}"
                    )
                detector = detector or TextDetector(
                    detector_config(self.ocr_model_path)
                )
                image = self.load_image(path)
                check_cancelled(cancelled)
                boxes, scores = (
                    ([], [])
                    if image is None
                    else _detected(detector, image)
                )
                h, w = (
                    image.shape[:2]
                    if image is not None
                    else (0, 0)
                )
                record = TextPhoto(
                    path,
                    stat.st_size,
                    stat.st_mtime_ns,
                    boxes,
                    [False] * len(boxes),
                    [False] * len(boxes),
                    scores,
                    [],
                    w,
                    h,
                )
                output.append(record)
                fresh.append(record)

            progress(index, len(files), path.name)
            check_cancelled(cancelled)

        if fresh:
            suggest(output, fresh)
        return output

    @staticmethod
    def load_image(path: Path, grayscale=False):
        return cv2.imdecode(
            np.fromfile(str(path), np.uint8),
            cv2.IMREAD_GRAYSCALE
            if grayscale
            else cv2.IMREAD_COLOR,
        )

    def ensure_size(self, record: TextPhoto):
        if record.height and record.width:
            return record.height, record.width
        image = self.load_image(record.path, grayscale=True)
        record.height, record.width = (
            image.shape[:2]
            if image is not None
            else (1, 1)
        )
        return record.height, record.width

    def eligible_indices(
        self,
        record: TextPhoto,
        *,
        min_height,
        min_area,
        min_conf,
    ):
        h, w = self.ensure_size(record)
        result = []
        for index, box in enumerate(record.boxes):
            arr = np.asarray(box)
            box_height = max(
                1,
                np.ptp(arr[:, 1]),
            )
            area = abs(
                cv2.contourArea(
                    np.asarray(box, np.float32)
                )
            )
            confidence = (
                record.scores[index]
                if index < len(record.scores)
                else 1.0
            )
            if (
                box_height >= max(int(min_height), h * .004)
                and area >= max(int(min_area), h * w * .00001)
                and confidence >= float(min_conf)
            ):
                result.append(index)
        return result

    @staticmethod
    def build_mask(record: TextPhoto, image: np.ndarray, expand: int):
        mask = np.zeros(image.shape[:2], np.uint8)
        for box, enabled in zip(
            record.boxes,
            record.selected,
        ):
            if enabled:
                cv2.fillPoly(
                    mask,
                    [np.asarray(box, np.int32)],
                    255,
                )

        expand = max(0, int(expand))
        if expand:
            mask = cv2.dilate(
                mask,
                cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE,
                    (expand * 2 + 1, expand * 2 + 1),
                ),
            )
        return mask

    def migan_ready(self):
        return model_exists(
            self.model_cache,
            self.model_reuse_roots,
        )

    def _migan(self):
        if self._repair_model is None:
            model = ensure_migan(
                self.model_cache,
                self.model_reuse_roots,
            )
            self._repair_model = MIRepair(model)
        return self._repair_model

    def repair_image(
        self,
        record: TextPhoto,
        image: np.ndarray,
        *,
        method,
        expand,
        radius,
    ):
        mask = self.build_mask(record, image, expand)
        if not np.any(mask):
            return image.copy()

        if method == AI_METHOD:
            return self._migan().run(image, mask)

        flag = (
            cv2.INPAINT_TELEA
            if method == TELEA_METHOD
            else cv2.INPAINT_NS
        )
        return cv2.inpaint(
            image,
            mask,
            int(radius),
            flag,
        )

    def repair_record(
        self,
        record: TextPhoto,
        *,
        method,
        expand,
        radius,
    ):
        image = self.load_image(record.path)
        if image is None:
            return None
        return self.repair_image(
            record,
            image,
            method=method,
            expand=expand,
            radius=radius,
        )

    def batch_process(
        self,
        *,
        folder: Path,
        output: Path,
        records,
        method,
        expand,
        radius,
        progress=None,
    ):
        folder = Path(folder).resolve()
        output = Path(output).resolve()
        progress = progress or (
            lambda _current, _total, _name: None
        )

        if (
            output == folder
            or folder in output.parents
        ):
            raise ValueError(
                "输出目录必须是源目录以外的新目录。"
            )

        output.mkdir(parents=True, exist_ok=True)
        written = 0

        for index, record in enumerate(records, 1):
            destination = output / record.path.resolve().relative_to(folder)
            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            image = (
                self.repair_record(
                    record,
                    method=method,
                    expand=expand,
                    radius=radius,
                )
                if any(record.selected)
                else self.load_image(record.path)
            )

            if image is not None:
                suffix = (
                    ".webp"
                    if record.path.suffix.lower() == ".webp"
                    else record.path.suffix
                )
                ok, encoded = cv2.imencode(suffix, image)
                if ok:
                    encoded.tofile(str(destination))
                    written += 1

            progress(
                index,
                len(records),
                record.path.name,
            )

        return TextCleanupBatchResult(written=written)


def self_test():
    with TemporaryDirectory() as td:
        sandbox = Path(td)
        root = sandbox / "source"
        root.mkdir()
        image_path = root / "sample.png"
        image = np.full((100, 160, 3), 180, np.uint8)
        cv2.rectangle(image, (20, 75), (140, 88), (10, 10, 10), -1)
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Text Cleanup test image encode failed.")
        encoded.tofile(str(image_path))

        stat = image_path.stat()
        record = TextPhoto(
            image_path,
            stat.st_size,
            stat.st_mtime_ns,
            boxes=[[[20, 75], [140, 75], [140, 88], [20, 88]]],
            selected=[True],
            manual=[False],
            scores=[.95],
            suggested=[],
            width=160,
            height=100,
        )
        suggest([record], [record])
        if record.suggested != [True]:
            raise RuntimeError(
                f"Text Cleanup suggestion regression: {record.suggested}"
            )

        state_path = root / "subtitle_cleaner.json"
        service = TextCleanupService(
            ocr_model_path=root / "missing.onnx",
            state_path=state_path,
            model_cache=root / "models",
        )
        service.save_state(
            folder=root,
            output=root.parent / "out",
            records=[record],
            method=TELEA_METHOD,
            expand=5,
            radius=4,
            min_height=6,
            min_area=36,
            min_conf=.0,
        )
        restored = service.load_state()
        if (
            restored.method != TELEA_METHOD
            or len(restored.records) != 1
            or restored.records[0].boxes != record.boxes
        ):
            raise RuntimeError("Text Cleanup state roundtrip failed.")

        cached = service.scan_folder(
            root,
            cached=service.state_records(root),
        )
        if len(cached) != 1 or cached[0].boxes != record.boxes:
            raise RuntimeError("Text Cleanup cached scan failed.")

        source = service.load_image(image_path)
        telea = service.repair_image(
            record,
            source,
            method=TELEA_METHOD,
            expand=1,
            radius=2,
        )
        ns = service.repair_image(
            record,
            source,
            method=NS_METHOD,
            expand=1,
            radius=2,
        )
        if telea.shape != source.shape or ns.shape != source.shape:
            raise RuntimeError("Text Cleanup inpaint smoke failed.")

        output = sandbox / "batch"
        result = service.batch_process(
            folder=root,
            output=output,
            records=[record],
            method=TELEA_METHOD,
            expand=1,
            radius=2,
        )
        if result.written != 1 or not (output / "sample.png").exists():
            raise RuntimeError("Text Cleanup batch output smoke failed.")

    print("Text Cleanup backend self-test OK")
