"""Pure quality-analysis backend for the ranking feature.

No Qt imports. The presentation layer may run this engine in any worker/thread
mechanism and receive progress through callbacks.
"""
from __future__ import annotations

import math
import pickle
import shutil
import tempfile
import urllib.request
import uuid
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.image import Image as MPImage, ImageFormat as MPImageFormat
from mediapipe.tasks.python.vision.pose_landmarker import (
    PoseLandmarker,
    PoseLandmarkerOptions,
)
from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
    VisionTaskRunningMode,
)

from core.models import AnalysisFinding, FaceDetection, Photo, derive_eligibility
from infrastructure.filesystem import sha256_file
from .service import rank

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS = PROJECT_ROOT / "models"
POSE = MODELS / "pose_landmarker_lite.task"
YUNET = MODELS / "yunet_2023mar.onnx"
EDIFF = MODELS / "ediffiqa_t.onnx"
BRISQUE = MODELS / "brisque_model_live.yml"
BRISQUE_RANGE = MODELS / "brisque_range_live.yml"
DDDFA = MODELS / "mb1_120x120.onnx"
DDDFA_NORM = MODELS / "param_mean_std_62d_120x120.pkl"
POSE_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)


def required(paths):
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError("缺少模型文件：\n" + "\n".join(missing))


def ensure_pose():
    if not POSE.exists():
        POSE.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(POSE_URL, POSE)
    run = Path(tempfile.gettempdir()) / "face_lora_selector" / POSE.name
    run.parent.mkdir(exist_ok=True)
    if not run.exists() or run.stat().st_size != POSE.stat().st_size:
        shutil.copy2(POSE, run)
    return run


def native_model(path):
    """Give native OpenCV layers an ASCII runtime path on Windows."""
    run = Path(tempfile.gettempdir()) / "face_lora_selector" / path.name
    run.parent.mkdir(exist_ok=True)
    if not run.exists() or run.stat().st_size != path.stat().st_size:
        shutil.copy2(path, run)
    return run


def new_sample_id():
    return "img_" + uuid.uuid4().hex[:20]


def phash_int(image):
    """64-bit pHash compatible with the historical ImageHash scipy DCT path."""
    gray = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    dct = cv2.dct(np.asarray(gray, dtype=np.float32))
    scale = np.full(32, math.sqrt(64.0), dtype=np.float32)
    scale[0] = 2.0 * math.sqrt(32.0)
    low = (dct * scale[:, None] * scale[None, :])[:8, :8]
    bits = (low > np.median(low)).reshape(-1)
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def yaw_class(yaw):
    if abs(yaw) < 15:
        return "正脸"
    return ("左" if yaw > 0 else "右") + ("3/4" if abs(yaw) < 45 else "侧脸")


def pitch_class(pitch):
    return "仰头" if pitch >= 22 else ("低头" if pitch <= -12 else "正常")


def person_scale(points):
    if not points:
        return "近景/头肩"

    def good(ids):
        return any(
            0 <= points[i].x <= 1
            and 0 <= points[i].y <= 1
            and getattr(points[i], "visibility", 0) >= 0.45
            for i in ids
        )

    if good((27, 28)):
        return "全身"
    if good((25, 26)):
        return "大半身"
    if good((23, 24)):
        return "半身"
    return "近景/头肩"


def face_box_intersection(a, b):
    ax, ay, aw, ah = map(float, a[:4])
    bx, by, bw, bh = map(float, b[:4])
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def dedupe_face_rows(rows):
    rows = [] if rows is None else list(rows)
    if len(rows) < 2:
        return rows
    ordered = sorted(rows, key=lambda f: float(f[2] * f[3]), reverse=True)
    kept = []
    for face in ordered:
        area = max(1.0, float(face[2] * face[3]))
        drop = False
        for previous in kept:
            previous_area = max(1.0, float(previous[2] * previous[3]))
            inter = face_box_intersection(face, previous)
            small = min(area, previous_area)
            union = area + previous_area - inter
            iou = inter / max(1.0, union)
            contain = inter / max(1.0, small)
            if iou >= 0.45 or contain >= 0.82:
                drop = True
                break
        if not drop:
            kept.append(face)
    return kept


def pose_head_roi(points, width, height):
    if not points:
        return None

    def valid(index, min_vis=0.25):
        point = points[index]
        return (
            0 <= point.x <= 1
            and 0 <= point.y <= 1
            and getattr(point, "visibility", 1) >= min_vis
        )

    head = [
        points[i]
        for i in range(0, 11)
        if i < len(points) and valid(i)
    ]
    if len(head) < 2:
        return None

    xs = [point.x * width for point in head]
    ys = [point.y * height for point in head]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    shoulder = 0.0
    if len(points) > 12 and valid(11, 0.2) and valid(12, 0.2):
        dx = (points[11].x - points[12].x) * width
        dy = (points[11].y - points[12].y) * height
        shoulder = math.hypot(dx, dy)

    rw = max(70.0, span_x * 2.4, shoulder * 0.9)
    rh = max(90.0, span_y * 3.2, shoulder * 1.05)
    return (
        max(0.0, cx - rw * 0.5),
        max(0.0, cy - rh * 0.55),
        min(float(width), cx + rw * 0.5),
        min(float(height), cy + rh * 0.45),
    )


def filter_face_rows_by_head(rows, roi):
    rows = [] if rows is None else list(rows)
    if not roi:
        return rows
    x0, y0, x1, y1 = roi
    out = []
    for face in rows:
        x, y, width, height = map(float, face[:4])
        cx, cy = x + width * 0.5, y + height * 0.5
        inter = max(0.0, min(x + width, x1) - max(x, x0)) * max(
            0.0, min(y + height, y1) - max(y, y0)
        )
        area = max(1.0, width * height)
        if (x0 <= cx <= x1 and y0 <= cy <= y1) or inter / area >= 0.35:
            out.append(face)
    return out


def consolidate_face_rows(rows, roi):
    rows = dedupe_face_rows(filter_face_rows_by_head(rows, roi))
    if roi and len(rows) > 1:
        def score(face):
            area = max(1.0, float(face[2] * face[3]))
            confidence = float(face[-1]) if len(face) > 14 else 1.0
            return area * max(0.01, confidence)

        return [max(rows, key=score)]
    return rows


class QualityModels:
    pts = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        np.float32,
    )

    def __init__(self):
        required([YUNET, EDIFF, BRISQUE, BRISQUE_RANGE, DDDFA, DDDFA_NORM])
        self.yunet_path = native_model(YUNET)
        self.brisque_model = native_model(BRISQUE)
        self.brisque_range = native_model(BRISQUE_RANGE)
        self.det = cv2.FaceDetectorYN.create(
            str(self.yunet_path), "", (320, 320), 0.7, 0.3, 5000
        )
        self.det_fallback = cv2.FaceDetectorYN.create(
            str(self.yunet_path), "", (320, 320), 0.45, 0.3, 5000
        )
        self.fq = ort.InferenceSession(
            str(EDIFF), providers=["CPUExecutionProvider"]
        )
        self.fqin = self.fq.get_inputs()[0].name
        self.pose = ort.InferenceSession(
            str(DDDFA), providers=["CPUExecutionProvider"]
        )
        self.posein = self.pose.get_inputs()[0].name
        with DDDFA_NORM.open("rb") as handle:
            norm = pickle.load(handle)
        self.mean = norm["mean"].astype(np.float32)
        self.std = norm["std"].astype(np.float32)

    def faces(self, image, fallback=False):
        detector = self.det_fallback if fallback else self.det
        detector.setInputSize((image.shape[1], image.shape[0]))
        return detector.detect(image)[1]

    @staticmethod
    def crop(image, roi):
        sx, sy, ex, ey = map(lambda x: int(round(x)), roi)
        out = np.zeros((max(1, ey - sy), max(1, ex - sx), 3), np.uint8)
        height, width = image.shape[:2]
        x0, x1 = max(0, sx), min(width, ex)
        y0, y1 = max(0, sy), min(height, ey)
        if x1 > x0 and y1 > y0:
            out[y0 - sy:y1 - sy, x0 - sx:x1 - sx] = image[y0:y1, x0:x1]
        return out

    def quality(self, image, face):
        transform, _ = cv2.estimateAffinePartial2D(
            face[4:14].reshape(5, 2).astype(np.float32),
            self.pts,
            method=cv2.LMEDS,
        )
        if transform is None:
            return 0.0
        rgb = cv2.cvtColor(
            cv2.warpAffine(image, transform, (112, 112)),
            cv2.COLOR_BGR2RGB,
        ).astype(np.float32)
        data = np.transpose((rgb / 255 - 0.5) / 0.5, (2, 0, 1))[None].astype(
            np.float32
        )
        return float(np.squeeze(self.fq.run(None, {self.fqin: data})[0]))

    def brisque(self, image):
        value = cv2.quality.QualityBRISQUE_compute(
            image, str(self.brisque_model), str(self.brisque_range)
        )
        return float(value[0] if isinstance(value, tuple) else value[0])

    def head(self, image, face):
        x, y, width, height = map(float, face[:4])
        old = (width + height) / 2
        cx, cy = x + width / 2, y + height / 2 + old * 0.14
        size = int(old * 1.58)
        crop = cv2.resize(
            self.crop(
                image,
                (
                    cx - size / 2,
                    cy - size / 2,
                    cx + size / 2,
                    cy + size / 2,
                ),
            ),
            (120, 120),
        ).astype(np.float32)
        output = (
            self.pose.run(
                None,
                {self.posein: ((crop - 127.5) / 128).transpose(2, 0, 1)[None]},
            )[0][0]
            * self.std
            + self.mean
        )
        rotation = output[:12].reshape(3, 4)[:, :3]
        r1 = rotation[0] / np.linalg.norm(rotation[0])
        r2 = rotation[1] / np.linalg.norm(rotation[1])
        rotation = np.stack((r1, r2, np.cross(r1, r2)))
        yaw = math.degrees(math.asin(np.clip(rotation[2, 0], -1, 1)))
        cosine = max(1e-6, math.cos(math.radians(yaw)))
        pitch = math.degrees(
            math.atan2(rotation[2, 1] / cosine, rotation[2, 2] / cosine)
        )
        roll = math.degrees(
            math.atan2(rotation[1, 0] / cosine, rotation[0, 0] / cosine)
        )
        return yaw, pitch, roll


class AnalysisEngine:
    def __init__(self):
        self.models = QualityModels()
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ensure_pose())),
            running_mode=VisionTaskRunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
        )
        self.pose_landmarker = PoseLandmarker.create_from_options(options)

    def close(self):
        self.pose_landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def analyze_one(self, path, size, mtime, content_sha=None):
        record = Photo(path, size, mtime)
        record.content_sha256 = content_sha or sha256_file(path)
        record.sample_id = new_sample_id()

        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                record.width, record.height = image.size
                record.phash = phash_int(image)
                rgb = np.asarray(image)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            record.brightness = float(gray.mean())
        except Exception as exc:
            record.hard_rejects.append(
                AnalysisFinding(
                    "read_error",
                    "image",
                    detail=f"无法读取图片：{exc}",
                )
            )
            derive_eligibility(record)
            return record

        pose_points = None
        head_roi = None
        try:
            pose = self.pose_landmarker.detect(
                MPImage(image_format=MPImageFormat.SRGB, data=rgb)
            )
            pose_points = pose.pose_landmarks[0] if pose.pose_landmarks else None
            record.person_scale = person_scale(pose_points)
            head_roi = pose_head_roi(
                pose_points, record.width, record.height
            )
            if head_roi:
                record.analysis_metrics["pose_head_roi"] = [
                    round(float(value), 2) for value in head_roi
                ]
        except Exception as exc:
            record.review_flags.append(
                AnalysisFinding(
                    "pose_analysis_error",
                    "mediapipe",
                    detail=f"景别/姿态分析失败：{exc}",
                )
            )

        rows = []
        face_fallback_used = False
        try:
            faces = self.models.faces(bgr)
            rows = consolidate_face_rows(faces, head_roi)
            if not rows and head_roi:
                faces = self.models.faces(bgr, True)
                rows = consolidate_face_rows(faces, head_roi)
                face_fallback_used = bool(rows)
        except Exception as exc:
            record.review_flags.append(
                AnalysisFinding(
                    "face_detection_error",
                    "yunet",
                    detail=f"人脸检测失败：{exc}",
                )
            )

        for index, face in enumerate(rows):
            x, y, width, height = map(float, face[:4])
            confidence = float(face[-1]) if len(face) > 14 else 1.0
            record.face_detections.append(
                FaceDetection(
                    f"face_{index + 1}",
                    [x, y, width, height],
                    confidence,
                    width * height / max(1, record.width * record.height),
                    int(min(width, height)),
                    False,
                    "yunet_fallback" if face_fallback_used else "yunet",
                )
            )
        record.faces = len(record.face_detections)

        if rows:
            primary_index = max(
                range(len(rows)),
                key=lambda i: record.face_detections[i].area_ratio
                * max(0.01, record.face_detections[i].confidence),
            )
            record.face_detections[primary_index].is_primary = True
            record.primary_face_id = record.face_detections[
                primary_index
            ].detection_id
            face = rows[primary_index]
            detection = record.face_detections[primary_index]
            x, y, width, height = map(float, face[:4])
            left, top = max(0, int(x)), max(0, int(y))
            right = min(record.width, int(x + width))
            bottom = min(record.height, int(y + height))
            record.face_ratio = detection.area_ratio
            record.face_px = detection.face_px

            try:
                crop = gray[top:bottom, left:right]
                record.blur = (
                    float(cv2.Laplacian(crop, cv2.CV_64F).var())
                    if crop.size
                    else 0.0
                )
            except Exception as exc:
                record.review_flags.append(
                    AnalysisFinding(
                        "face_sharpness_error",
                        "opencv",
                        detail=f"主脸清晰度分析失败：{exc}",
                    )
                )
            try:
                record.face_quality = self.models.quality(bgr, face)
            except Exception as exc:
                record.review_flags.append(
                    AnalysisFinding(
                        "face_quality_error",
                        "ediffiqa",
                        detail=f"eDifFIQA 分析失败：{exc}",
                    )
                )
            try:
                record.yaw, record.pitch, record.roll = self.models.head(bgr, face)
                record.angle_class = yaw_class(record.yaw)
                record.pitch_class = pitch_class(record.pitch)
            except Exception as exc:
                record.review_flags.append(
                    AnalysisFinding(
                        "head_pose_error",
                        "3ddfa",
                        detail=f"头部姿态分析失败：{exc}",
                    )
                )
        else:
            try:
                record.blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            except Exception:
                pass

        try:
            record.brisque = self.models.brisque(bgr)
        except Exception as exc:
            record.review_flags.append(
                AnalysisFinding(
                    "brisque_error",
                    "brisque",
                    detail=f"BRISQUE 分析失败：{exc}",
                )
            )

        dark = float((gray < 20).mean())
        bright = float((gray > 235).mean())
        record.analysis_metrics.update(
            {
                "dark_fraction": dark,
                "bright_fraction": bright,
                "face_count": record.faces,
                "face_detector_fallback": face_fallback_used,
            }
        )

        if record.faces == 0:
            if record.person_scale == "全身":
                record.review_flags.append(
                    AnalysisFinding(
                        "no_face_full_body_review",
                        "yunet",
                        detail="未检测到人脸，但检测到全身；可能是有价值的背身/背面素材，需人工确认",
                    )
                )
            else:
                record.hard_rejects.append(
                    AnalysisFinding(
                        "no_face_not_full_body",
                        "yunet",
                        detail="两个检测阈值均未找到人脸，且不是全身图",
                    )
                )
        elif record.faces > 1:
            record.review_flags.append(
                AnalysisFinding(
                    "secondary_faces_detected",
                    "yunet",
                    float(record.faces),
                    1.0,
                    f"去重后仍检测到 {record.faces} 张独立人脸，需确认是否多人",
                )
            )

        if record.width < 512 or record.height < 512:
            record.review_flags.append(
                AnalysisFinding(
                    "low_resolution",
                    "image",
                    float(min(record.width, record.height)),
                    512.0,
                    "图片短边分辨率低于 512px",
                )
            )
        if rows and record.face_px < 120:
            record.review_flags.append(
                AnalysisFinding(
                    "low_face_pixels",
                    "primary_face",
                    float(record.face_px),
                    120.0,
                    "主脸实际像素偏小",
                )
            )
        if rows and record.face_ratio < 0.018:
            record.review_flags.append(
                AnalysisFinding(
                    "low_face_ratio",
                    "primary_face",
                    record.face_ratio,
                    0.018,
                    "主脸占画面比例偏低",
                )
            )
        if rows and record.blur < 25:
            record.review_flags.append(
                AnalysisFinding(
                    "severe_face_blur",
                    "primary_face",
                    record.blur,
                    25.0,
                    "主脸明显模糊",
                )
            )
        if rows and record.face_quality < 0.25:
            record.review_flags.append(
                AnalysisFinding(
                    "low_face_quality",
                    "ediffiqa",
                    record.face_quality,
                    0.25,
                    "eDifFIQA 人脸质量偏低",
                )
            )
        if record.brisque > 80:
            record.review_flags.append(
                AnalysisFinding(
                    "high_brisque",
                    "brisque",
                    record.brisque,
                    80.0,
                    "BRISQUE 整图质量偏低",
                )
            )
        if (
            record.brightness < 28
            or record.brightness > 228
            or dark > 0.55
            or bright > 0.55
        ):
            record.review_flags.append(
                AnalysisFinding(
                    "extreme_exposure",
                    "image",
                    record.brightness,
                    None,
                    "图像疑似严重欠曝或过曝",
                )
            )

        derive_eligibility(record)
        return record


def group_duplicates(records, threshold=8, adjacent=16):
    """Anchor-based pHash grouping; no transitive chain merging."""
    for record in records:
        record.duplicate_group = 0
    remaining = {
        index
        for index, record in enumerate(records)
        if record.phash and not record.duplicate_ignore
    }
    group_no = 1
    while remaining:
        anchor = max(remaining, key=lambda i: rank(records[i]))
        remaining.remove(anchor)
        members = [anchor]
        for candidate in list(remaining):
            left, right = records[anchor], records[candidate]
            distance = bin(left.phash ^ right.phash).count("1")
            same_source = left.source == right.source
            close = distance <= threshold or (
                same_source
                and distance <= adjacent
                and left.person_scale == right.person_scale
                and abs(left.yaw - right.yaw) <= 25
                and abs(left.pitch - right.pitch) <= 25
            )
            if close:
                members.append(candidate)
                remaining.remove(candidate)
        if len(members) > 1:
            for index in members:
                records[index].duplicate_group = group_no
            group_no += 1


def base_status(records):
    for record in records:
        if record.manual_status is None:
            record.auto_status = (
                "淘汰" if record.eligibility == "REJECT" else "备选"
            )


def pose_smoke_test():
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_pose())),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
    )
    landmarker = PoseLandmarker.create_from_options(options)
    landmarker.close()
