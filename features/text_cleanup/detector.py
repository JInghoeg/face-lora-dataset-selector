# Copyright (c) 2020 PaddlePaddle Authors.
# Portions adapted from RapidOCR / PaddleOCR DB text detection post-processing.
# Licensed under the Apache License, Version 2.0.
"""Minimal PP-OCR DB text detector used by Face LoRA Dataset Selector.

This module intentionally contains only the detection preprocessing / DB
post-processing needed by the application. Inference uses the project's own
PP-OCRv5 ONNX model through ONNX Runtime.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort
import pyclipper


class ResizeImgError(Exception):
    pass


class DetPreProcess:
    def __init__(
        self,
        limit_side_len: int = 736,
        limit_type: str = "min",
        mean=None,
        std=None,
    ):
        self.mean = np.asarray(mean or [0.5, 0.5, 0.5], dtype=np.float32)
        self.std = np.asarray(std or [0.5, 0.5, 0.5], dtype=np.float32)
        self.scale = 1.0 / 255.0
        self.limit_side_len = limit_side_len
        self.limit_type = limit_type

    def __call__(self, img: np.ndarray) -> Optional[np.ndarray]:
        resized = self.resize(img)
        if resized is None:
            return None
        normalized = (resized.astype("float32") * self.scale - self.mean) / self.std
        normalized = normalized.transpose((2, 0, 1))
        return np.expand_dims(normalized, axis=0).astype(np.float32)

    def resize(self, img: np.ndarray) -> Optional[np.ndarray]:
        h, w = img.shape[:2]
        if self.limit_type == "max":
            ratio = min(1.0, float(self.limit_side_len) / max(h, w))
        else:
            ratio = max(1.0, float(self.limit_side_len) / min(h, w))

        resize_h = int(round((h * ratio) / 32) * 32)
        resize_w = int(round((w * ratio) / 32) * 32)
        if resize_w <= 0 or resize_h <= 0:
            return None
        try:
            return cv2.resize(img, (resize_w, resize_h))
        except Exception as exc:
            raise ResizeImgError from exc


class DBPostProcess:
    """Differentiable Binarization (DB) text detection post-process."""

    def __init__(
        self,
        thresh: float = 0.3,
        box_thresh: float = 0.7,
        max_candidates: int = 1000,
        unclip_ratio: float = 2.0,
        score_mode: str = "fast",
        use_dilation: bool = False,
    ):
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio
        self.min_size = 3
        self.score_mode = score_mode
        self.dilation_kernel = np.array([[1, 1], [1, 1]], dtype=np.uint8) if use_dilation else None

    def __call__(
        self, pred: np.ndarray, ori_shape: Tuple[int, int]
    ) -> Tuple[np.ndarray, List[float]]:
        src_h, src_w = ori_shape
        pred = pred[:, 0, :, :]
        segmentation = pred > self.thresh
        mask = segmentation[0]
        if self.dilation_kernel is not None:
            mask = cv2.dilate(mask.astype(np.uint8), self.dilation_kernel)
        return self.boxes_from_bitmap(pred[0], mask, src_w, src_h)

    def boxes_from_bitmap(
        self, pred: np.ndarray, bitmap: np.ndarray, dest_width: int, dest_height: int
    ) -> Tuple[np.ndarray, List[float]]:
        height, width = bitmap.shape
        contours, _ = cv2.findContours(
            (bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        boxes, scores = [], []
        for contour in contours[: self.max_candidates]:
            points, short_side = self.get_mini_boxes(contour)
            if short_side < self.min_size:
                continue

            score = (
                self.box_score_fast(pred, points.reshape(-1, 2))
                if self.score_mode == "fast"
                else self.box_score_slow(pred, contour)
            )
            if score < self.box_thresh:
                continue

            expanded = self.unclip(points)
            if expanded.size == 0:
                continue
            box, short_side = self.get_mini_boxes(expanded)
            if short_side < self.min_size + 2:
                continue

            box[:, 0] = np.clip(
                np.round(box[:, 0] / width * dest_width), 0, dest_width
            )
            box[:, 1] = np.clip(
                np.round(box[:, 1] / height * dest_height), 0, dest_height
            )
            boxes.append(box.astype(np.int32))
            scores.append(float(score))

        return np.asarray(boxes, dtype=np.int32), scores

    @staticmethod
    def get_mini_boxes(contour: np.ndarray) -> Tuple[np.ndarray, float]:
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])
        if points[1][1] > points[0][1]:
            i1, i4 = 0, 1
        else:
            i1, i4 = 1, 0
        if points[3][1] > points[2][1]:
            i2, i3 = 2, 3
        else:
            i2, i3 = 3, 2
        box = np.asarray([points[i1], points[i2], points[i3], points[i4]], dtype=np.float32)
        return box, min(bounding_box[1])

    @staticmethod
    def box_score_fast(bitmap: np.ndarray, box: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        box = box.copy()
        xmin = np.clip(np.floor(box[:, 0].min()).astype(np.int32), 0, w - 1)
        xmax = np.clip(np.ceil(box[:, 0].max()).astype(np.int32), 0, w - 1)
        ymin = np.clip(np.floor(box[:, 1].min()).astype(np.int32), 0, h - 1)
        ymax = np.clip(np.ceil(box[:, 1].max()).astype(np.int32), 0, h - 1)
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box[:, 0] -= xmin
        box[:, 1] -= ymin
        cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0])

    @staticmethod
    def box_score_slow(bitmap: np.ndarray, contour: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        contour = np.reshape(contour.copy(), (-1, 2))
        xmin = int(np.clip(np.min(contour[:, 0]), 0, w - 1))
        xmax = int(np.clip(np.max(contour[:, 0]), 0, w - 1))
        ymin = int(np.clip(np.min(contour[:, 1]), 0, h - 1))
        ymax = int(np.clip(np.max(contour[:, 1]), 0, h - 1))
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        contour[:, 0] -= xmin
        contour[:, 1] -= ymin
        cv2.fillPoly(mask, contour.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0])

    def unclip(self, box: np.ndarray) -> np.ndarray:
        contour = np.asarray(box, dtype=np.float32).reshape(-1, 1, 2)
        area = abs(float(cv2.contourArea(contour)))
        length = float(cv2.arcLength(contour, True))
        if area <= 0 or length <= 0:
            return np.empty((0, 1, 2), dtype=np.float32)

        distance = area * self.unclip_ratio / length
        offset = pyclipper.PyclipperOffset()
        offset.AddPath(
            np.rint(box).astype(np.int32).tolist(),
            pyclipper.JT_ROUND,
            pyclipper.ET_CLOSEDPOLYGON,
        )
        expanded = offset.Execute(distance)
        if not expanded:
            return np.empty((0, 1, 2), dtype=np.float32)

        best = max(
            expanded,
            key=lambda p: abs(
                cv2.contourArea(np.asarray(p, dtype=np.float32).reshape(-1, 1, 2))
            ),
        )
        return np.asarray(best, dtype=np.float32).reshape(-1, 1, 2)


class TextDetector:
    """PP-OCR detection wrapper with the subset of RapidOCR's old API we use."""

    def __init__(self, config: Dict[str, Any]):
        self.limit_type = config.get("limit_type", "min")
        self.limit_side_len = int(config.get("limit_side_len", 736))
        self.mean = config.get("mean", [0.5, 0.5, 0.5])
        self.std = config.get("std", [0.5, 0.5, 0.5])
        self.preprocess_op = None

        self.postprocess_op = DBPostProcess(
            thresh=float(config.get("thresh", 0.3)),
            box_thresh=float(config.get("box_thresh", 0.5)),
            max_candidates=int(config.get("max_candidates", 1000)),
            unclip_ratio=float(config.get("unclip_ratio", 1.6)),
            use_dilation=bool(config.get("use_dilation", True)),
            score_mode=config.get("score_mode", "fast"),
        )

        options = ort.SessionOptions()
        intra = int(config.get("intra_op_num_threads", -1))
        inter = int(config.get("inter_op_num_threads", -1))
        if intra > 0:
            options.intra_op_num_threads = intra
        if inter > 0:
            options.inter_op_num_threads = inter

        self.session = ort.InferenceSession(
            str(config["model_path"]),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name

    def infer(self, image: np.ndarray):
        return self.session.run(None, {self.input_name: image})

    def get_preprocess(self, max_wh: int):
        if self.limit_type == "min":
            limit_side_len = self.limit_side_len
        elif max_wh < 960:
            limit_side_len = 960
        elif max_wh < 1500:
            limit_side_len = 1500
        else:
            limit_side_len = 2000
        return DetPreProcess(limit_side_len, self.limit_type, self.mean, self.std)

    def filter_tag_det_res(
        self, dt_boxes: np.ndarray, image_shape: Tuple[int, int]
    ) -> np.ndarray:
        img_height, img_width = image_shape
        result = []
        for box in dt_boxes:
            box = self.order_points_clockwise(box)
            box = self.clip_det_res(box, img_height, img_width)
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= 3 or rect_height <= 3:
                continue
            result.append(box)
        return np.asarray(result)

    @staticmethod
    def order_points_clockwise(pts: np.ndarray) -> np.ndarray:
        x_sorted = pts[np.argsort(pts[:, 0]), :]
        left = x_sorted[:2, :]
        right = x_sorted[2:, :]
        left = left[np.argsort(left[:, 1]), :]
        tl, bl = left
        right = right[np.argsort(right[:, 1]), :]
        tr, br = right
        return np.asarray([tl, tr, br, bl], dtype=np.float32)

    @staticmethod
    def clip_det_res(
        points: np.ndarray, img_height: int, img_width: int
    ) -> np.ndarray:
        points = points.copy()
        points[:, 0] = np.clip(points[:, 0], 0, img_width - 1)
        points[:, 1] = np.clip(points[:, 1], 0, img_height - 1)
        return points
