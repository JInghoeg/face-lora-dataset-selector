"""Auto Crop research harness v0.

This is intentionally separate from the production selector UI.  It reuses the
already-bundled MediaPipe Pose model and OpenCV saliency to test a conservative
"safe trim" baseline on real character images.

The harness never edits source images.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time
import traceback
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path

# Windows terminals often default to GBK/cp936. Dataset filenames may contain
# CJK/Korean/Japanese characters, so keep diagnostic output UTF-8-safe.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.image import Image as MPImage, ImageFormat as MPImageFormat
from mediapipe.tasks.python.vision.pose_landmarker import PoseLandmarker, PoseLandmarkerOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

# Allow direct execution as `python research/auto_crop_harness.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Reuse project models/cache semantics instead of creating a parallel stack.
from app import EXT, ensure_pose, load_data, key

HARNESS_VERSION = 1
REVIEW_SIZE_DEFAULT = 72
ANALYSIS_MAX_SIDE = 1280
RESEARCH_ROOT = (
    Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    / "Face LoRA Dataset Selector"
    / "research"
    / "auto_crop"
)

CROP_LABELS = [
    ("SAFE", "安全可用"),
    ("TOO_TIGHT", "太紧 / 切关键内容"),
    ("UNNECESSARY", "不该裁"),
    ("TOO_LOOSE", "太松"),
    ("MANUAL", "需要手调"),
]
KEEP_LABELS = [
    ("CORRECT_KEEP", "保留正确"),
    ("MISSED_CROP", "漏裁了"),
]


@dataclass
class CropProposal:
    path: str
    relative_path: str
    decision: str
    crop_box: list[int] | None
    width: int
    height: int
    trim_ratio: float
    potential_trim_ratio: float
    risk_score: float
    risk_level: str
    outside_saliency_fraction: float
    pose_present: bool
    segmentation_present: bool
    reason: list[str]
    selector_status: str = ""
    person_scale: str = ""
    angle_class: str = ""


def image_files(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXT),
        key=lambda p: str(p).casefold(),
    )


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        try:
            im.seek(0)
        except EOFError:
            pass
        im = ImageOps.exif_transpose(im).convert("RGB")
        return np.asarray(im)


def selector_record_map(folder: Path) -> dict[str, dict]:
    data = load_data(folder)
    out = {}
    for rec in data.get("records", []):
        if isinstance(rec, dict) and rec.get("path"):
            out[str(rec["path"]).casefold()] = rec
    return out


def effective_status(rec: dict | None) -> str:
    if not rec:
        return ""
    return rec.get("manual_status") or rec.get("auto_status") or ""


def selected_input_files(folder: Path, include_all: bool) -> tuple[list[Path], dict[str, dict], str, dict]:
    files = image_files(folder)
    records = selector_record_map(folder)
    tracked = [p for p in files if key(p) in records]
    recommended = [p for p in files if effective_status(records.get(key(p))) == "推荐"]
    stats = {
        "total_images": len(files),
        "tracked_images": len(tracked),
        "untracked_images": len(files) - len(tracked),
        "recommended_images": len(recommended),
    }

    if include_all or not records:
        stats["selected_images"] = len(files)
        return files, records, "all", stats
    if recommended:
        stats["selected_images"] = len(recommended)
        return recommended, records, "recommended", stats
    stats["selected_images"] = len(files)
    return files, records, "all_fallback", stats


def resize_for_saliency(bgr: np.ndarray, max_side: int = 1024) -> tuple[np.ndarray, float]:
    h, w = bgr.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale >= 0.999:
        return bgr, 1.0
    return cv2.resize(bgr, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA), scale


def saliency_map(bgr: np.ndarray) -> np.ndarray:
    work, scale = resize_for_saliency(bgr)
    detector = cv2.saliency.StaticSaliencyFineGrained_create()
    ok, sal = detector.computeSaliency(work)
    if not ok or sal is None:
        return np.zeros(bgr.shape[:2], np.float32)
    sal = np.asarray(sal, dtype=np.float32)
    if sal.ndim == 3:
        sal = sal[..., 0]
    if scale != 1.0:
        sal = cv2.resize(sal, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    sal = cv2.GaussianBlur(sal, (0, 0), sigmaX=max(1.0, min(bgr.shape[:2]) / 500.0))
    lo, hi = float(sal.min()), float(sal.max())
    if hi > lo:
        sal = (sal - lo) / (hi - lo)
    return sal


def disk_kernel(radius: int) -> np.ndarray:
    radius = max(1, int(radius))
    size = radius * 2 + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def rect_expand(box: tuple[int, int, int, int], width: int, height: int, mx: int, my: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return max(0, x0 - mx), max(0, y0 - my), min(width, x1 + mx), min(height, y1 + my)


def draw_landmark_protection(mask: np.ndarray, points, width: int, height: int) -> None:
    if not points:
        return
    r = max(6, round(min(width, height) * 0.025))
    for p in points:
        vis = float(getattr(p, "visibility", 1.0))
        if vis < 0.18 or not (0 <= p.x <= 1 and 0 <= p.y <= 1):
            continue
        cv2.circle(mask, (round(p.x * width), round(p.y * height)), r, 255, -1, cv2.LINE_AA)


def nearby_saliency_mask(sal: np.ndarray, hard: np.ndarray) -> tuple[np.ndarray, float]:
    """Keep only salient connected components that plausibly belong to the subject.

    This borrows smartcrop's protected/boosted-region principle, but does not force
    a target aspect ratio. Remote salient components remain a risk signal instead
    of automatically becoming protected content.
    """
    h, w = sal.shape
    if not np.any(hard):
        return np.zeros_like(hard), 0.0

    q = float(np.quantile(sal, 0.90))
    threshold = max(0.28, q)
    binary = (sal >= threshold).astype(np.uint8) * 255
    near = cv2.dilate(hard, disk_kernel(max(4, round(min(h, w) * 0.10))))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    kept = np.zeros_like(hard)
    min_area = max(12, round(h * w * 0.00012))
    for idx in range(1, n):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        component = labels == idx
        if np.any(component & (near > 0)):
            kept[component] = 255

    salient_total = max(1, int(np.count_nonzero(binary)))
    remote = np.count_nonzero((binary > 0) & (kept == 0))
    return kept, remote / salient_total


def pose_protection(result, width: int, height: int) -> tuple[np.ndarray, bool, bool]:
    hard = np.zeros((height, width), np.uint8)
    points = result.pose_landmarks[0] if result.pose_landmarks else None
    pose_present = points is not None
    seg_present = False

    if result.segmentation_masks:
        view = np.asarray(result.segmentation_masks[0].numpy_view(), dtype=np.float32)
        if view.ndim == 3:
            view = view[..., 0]
        view = cv2.resize(view, (width, height), interpolation=cv2.INTER_LINEAR)
        # A deliberately low threshold protects uncertain hair/clothing edges.
        hard[view >= 0.08] = 255
        seg_present = True

    draw_landmark_protection(hard, points, width, height)
    if np.any(hard):
        radius = max(5, round(min(width, height) * 0.025))
        hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, disk_kernel(max(2, radius // 2)))
        hard = cv2.dilate(hard, disk_kernel(radius))
    return hard, pose_present, seg_present


def crop_edge_density(mask: np.ndarray, crop: tuple[int, int, int, int], band: int) -> float:
    x0, y0, x1, y1 = crop
    band = max(1, band)
    region = np.zeros_like(mask, np.uint8)
    region[y0:min(y1, y0 + band), x0:x1] = 1
    region[max(y0, y1 - band):y1, x0:x1] = 1
    region[y0:y1, x0:min(x1, x0 + band)] = 1
    region[y0:y1, max(x0, x1 - band):x1] = 1
    denom = max(1, int(region.sum()))
    return float(np.count_nonzero((mask > 0) & (region > 0))) / denom


def resize_for_analysis(rgb: np.ndarray, max_side: int = ANALYSIS_MAX_SIDE) -> tuple[np.ndarray, float]:
    """Downscale only the in-memory analysis copy; source/export pixels stay untouched."""
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale >= 0.999:
        return np.ascontiguousarray(rgb, dtype=np.uint8), 1.0
    work = cv2.resize(
        rgb,
        (max(1, round(w * scale)), max(1, round(h * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return np.ascontiguousarray(work, dtype=np.uint8), scale


def pose_detect_padded(rgb: np.ndarray, landmarker: PoseLandmarker):
    """Run PoseLandmarker with width padded to a multiple of 4.

    MediaPipe 0.10.30+ has a native numpy_view() regression for float32
    segmentation masks whose row stride is non-contiguous. Padding by at most
    three right-edge pixels keeps mask width divisible by 4 and avoids the
    uncatchable native CHECK failure. The original image is never modified.
    """
    h, w = rgb.shape[:2]
    pad_right = (-w) % 4
    if pad_right:
        padded = cv2.copyMakeBorder(
            np.ascontiguousarray(rgb, dtype=np.uint8),
            0, 0, 0, pad_right,
            cv2.BORDER_REPLICATE,
        )
    else:
        padded = np.ascontiguousarray(rgb, dtype=np.uint8)

    mp_image = MPImage(image_format=MPImageFormat.SRGB, data=padded)
    result = landmarker.detect(mp_image)
    return result, padded.shape[1], pad_right


def propose(rgb: np.ndarray, landmarker: PoseLandmarker) -> dict:
    original_h, original_w = rgb.shape[:2]
    work_rgb, analysis_scale = resize_for_analysis(rgb)
    h, w = work_rgb.shape[:2]
    bgr = cv2.cvtColor(work_rgb, cv2.COLOR_RGB2BGR)
    result, pose_width, pad_right = pose_detect_padded(work_rgb, landmarker)

    hard, pose_present, seg_present = pose_protection(result, pose_width, h)
    if pad_right:
        hard = hard[:, :w]
    sal = saliency_map(bgr)
    nearby_sal, remote_saliency_fraction = nearby_saliency_mask(sal, hard)

    if not np.any(hard):
        return {
            "decision": "keep_original",
            "crop_box": None,
            "trim_ratio": 0.0,
            "potential_trim_ratio": 0.0,
            "risk_score": 1.0,
            "risk_level": "high",
            "outside_saliency_fraction": 1.0,
            "pose_present": pose_present,
            "segmentation_present": seg_present,
            "reason": ["未可靠检测到人物保护区域，保守保留原图"],
        }

    protected = cv2.bitwise_or(hard, nearby_sal)
    box = mask_bbox(protected)
    if box is None:
        return {
            "decision": "keep_original",
            "crop_box": None,
            "trim_ratio": 0.0,
            "potential_trim_ratio": 0.0,
            "risk_score": 1.0,
            "risk_level": "high",
            "outside_saliency_fraction": remote_saliency_fraction,
            "pose_present": pose_present,
            "segmentation_present": seg_present,
            "reason": ["保护区域为空，保守保留原图"],
        }

    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    # Generous subject margin: intentionally much looser than a tight person bbox.
    mx = max(round(w * 0.055), round(bw * 0.09), 16)
    my = max(round(h * 0.060), round(bh * 0.09), 16)
    crop = rect_expand(box, w, h, mx, my)
    x0, y0, x1, y1 = crop

    area = max(1, w * h)
    crop_area = max(1, (x1 - x0) * (y1 - y0))
    potential_trim = 1.0 - crop_area / area
    side_trim = {
        "left": x0 / w,
        "right": (w - x1) / w,
        "top": y0 / h,
        "bottom": (h - y1) / h,
    }

    sal_thresh = max(0.28, float(np.quantile(sal, 0.90)))
    salient = sal >= sal_thresh
    outside = np.ones((h, w), bool)
    outside[y0:y1, x0:x1] = False
    outside_sal = np.count_nonzero(salient & outside) / max(1, np.count_nonzero(salient))

    # Boundary density is a soft uncertainty signal, not a direct crop target.
    protected_edge_density = crop_edge_density(protected, crop, max(4, round(min(w, h) * 0.018)))
    risk = min(1.0, outside_sal * 1.6 + protected_edge_density * 1.8)
    level = "low" if risk < 0.12 else ("medium" if risk < 0.24 else "high")

    reasons = []
    meaningful_sides = [name for name, value in side_trim.items() if value >= 0.055]
    if meaningful_sides:
        reasons.append("可安全收掉较明显的外围：" + "、".join(meaningful_sides))
    if remote_saliency_fraction > 0.10:
        reasons.append("外围存在与人物未连接的显著内容")
    if level != "low":
        reasons.append(f"裁剪边界风险为 {level}")

    # Asymmetric safety policy: false keep is cheap, false crop is expensive.
    decision = "suggest_crop"
    if potential_trim < 0.12:
        decision = "keep_original"
        reasons = ["预计仅减少少量外围区域，收益不足"]
    elif potential_trim > 0.45:
        decision = "keep_original"
        reasons = ["建议框会移除过多画面，保守保留原图"]
    elif outside_sal > 0.13 or level == "high":
        decision = "keep_original"
        reasons.append("外围重要性不确定，保守保留原图")
    elif not meaningful_sides:
        decision = "keep_original"
        reasons = ["没有单侧达到值得裁剪的幅度"]

    if decision == "suggest_crop":
        inv = 1.0 / analysis_scale
        mapped_crop = [
            max(0, min(original_w, math.floor(x0 * inv))),
            max(0, min(original_h, math.floor(y0 * inv))),
            max(0, min(original_w, math.ceil(x1 * inv))),
            max(0, min(original_h, math.ceil(y1 * inv))),
        ]
    else:
        mapped_crop = None

    return {
        "decision": decision,
        "crop_box": mapped_crop,
        "trim_ratio": potential_trim if decision == "suggest_crop" else 0.0,
        "potential_trim_ratio": potential_trim,
        "risk_score": risk,
        "risk_level": level,
        "outside_saliency_fraction": outside_sal,
        "pose_present": pose_present,
        "segmentation_present": seg_present,
        "reason": reasons or ["保守保留原图"],
    }


def stable_random_key(path: str) -> int:
    return int(hashlib.sha256(path.encode("utf-8")).hexdigest()[:16], 16)


def choose_review_pack(proposals: list[dict], target: int) -> list[dict]:
    target = max(1, min(target, len(proposals)))
    crops = [p for p in proposals if p["decision"] == "suggest_crop"]
    keeps = [p for p in proposals if p["decision"] == "keep_original"]
    selected: dict[str, dict] = {}

    def take(items, count):
        for p in items:
            if len(selected) >= target:
                break
            if p["path"] not in selected:
                selected[p["path"]] = p
                count -= 1
                if count <= 0:
                    break

    take(sorted(crops, key=lambda p: p["trim_ratio"], reverse=True), max(10, target // 4))
    take(sorted(crops, key=lambda p: p["risk_score"], reverse=True), max(10, target // 4))
    take(sorted(crops, key=lambda p: stable_random_key(p["path"])), max(8, target // 5))
    take(sorted(keeps, key=lambda p: p["potential_trim_ratio"], reverse=True), max(10, target // 5))
    take(sorted(keeps, key=lambda p: stable_random_key(p["path"])), target)

    return list(selected.values())[:target]


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_proposals_csv(path: Path, proposals: list[dict]) -> None:
    fields = [
        "relative_path", "decision", "width", "height", "trim_ratio",
        "potential_trim_ratio", "risk_score", "risk_level",
        "outside_saliency_fraction", "pose_present", "segmentation_present",
        "selector_status", "person_scale", "angle_class", "crop_box", "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for p in proposals:
            row = {k: p.get(k, "") for k in fields}
            row["crop_box"] = json.dumps(row["crop_box"], ensure_ascii=False)
            row["reason"] = " | ".join(p.get("reason", []))
            writer.writerow(row)


def draw_crop_overlay(image: Image.Image, crop_box: list[int] | None) -> Image.Image:
    out = image.convert("RGB").copy()
    if not crop_box:
        return out
    x0, y0, x1, y1 = crop_box
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    shade = ImageDraw.Draw(overlay)
    shade.rectangle((0, 0, out.width, out.height), fill=(0, 0, 0, 105))
    shade.rectangle((x0, y0, x1, y1), fill=(0, 0, 0, 0))
    out = Image.alpha_composite(out.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(out)
    width = max(3, round(min(out.size) * 0.006))
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 80, 60), width=width)
    return out


def fit_tile(image: Image.Image, width: int, height: int) -> Image.Image:
    image = image.convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (28, 28, 28))
    canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    return canvas


def write_contact_sheets(run_dir: Path, pack: list[dict]) -> None:
    out = run_dir / "contact_sheets"
    out.mkdir(parents=True, exist_ok=True)
    cols, rows = 3, 3
    tile_w, tile_h = 420, 330
    for page_no, start in enumerate(range(0, len(pack), cols * rows), 1):
        page = Image.new("RGB", (cols * tile_w, rows * tile_h), "white")
        for slot, proposal in enumerate(pack[start:start + cols * rows]):
            row, col = divmod(slot, cols)
            x, y = col * tile_w, row * tile_h
            try:
                with Image.open(proposal["path"]) as im:
                    im.seek(0)
                    preview = draw_crop_overlay(ImageOps.exif_transpose(im), proposal.get("crop_box"))
                    tile = fit_tile(preview, tile_w - 12, tile_h - 58)
            except Exception:
                continue
            page.paste(tile, (x + 6, y + 6))
            draw = ImageDraw.Draw(page)
            text = f'{proposal["relative_path"][:48]} | {proposal["decision"]} | trim {proposal["potential_trim_ratio"]:.1%} | risk {proposal["risk_level"]}'
            draw.text((x + 8, y + tile_h - 44), text, fill="black")
        page.save(out / f"review_{page_no:03d}.jpg", quality=90)


def analyze(folder: Path, include_all: bool, review_size: int, progress=None) -> Path:
    files, records, scope, input_stats = selected_input_files(folder, include_all)
    if not files:
        raise RuntimeError("没有找到可分析图片。")
    scope_text = "全部图片" if scope.startswith("all") else "推荐图片"
    print(
        f"Input scope: folder_total={input_stats['total_images']} | "
        f"tracked={input_stats['tracked_images']} | "
        f"untracked={input_stats['untracked_images']} | "
        f"recommended={input_stats['recommended_images']} | "
        f"selected={input_stats['selected_images']} ({scope_text})",
        flush=True,
    )

    stamp = time.strftime("%Y%m%d_%H%M%S")
    folder_id = hashlib.sha256(key(folder).encode()).hexdigest()[:12]
    run_dir = RESEARCH_ROOT / folder_id / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_pose())),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.45,
        min_pose_presence_confidence=0.45,
        output_segmentation_masks=True,
    )

    proposals = []
    with PoseLandmarker.create_from_options(options) as landmarker:
        for index, path in enumerate(files, 1):
            print(f"[{index}/{len(files)}] {path.name}", flush=True)
            if progress:
                progress(
                    index,
                    len(files),
                    f"{path.name}\n文件夹共 {input_stats['total_images']} 张 · "
                    f"推荐 {input_stats['recommended_images']} · "
                    f"未入缓存 {input_stats['untracked_images']} · 本次 {scope_text} {len(files)}",
                )
            width = height = 0
            try:
                rgb = load_rgb(path)
                height, width = rgb.shape[:2]
                result = propose(rgb, landmarker)
            except Exception as exc:
                result = {
                    "decision": "keep_original",
                    "crop_box": None,
                    "trim_ratio": 0.0,
                    "potential_trim_ratio": 0.0,
                    "risk_score": 1.0,
                    "risk_level": "high",
                    "outside_saliency_fraction": 1.0,
                    "pose_present": False,
                    "segmentation_present": False,
                    "reason": [f"分析失败，保守保留原图：{exc}"],
                }

            rec = records.get(key(path))
            proposal = CropProposal(
                path=str(path.resolve()),
                relative_path=str(path.resolve().relative_to(folder.resolve())),
                width=width,
                height=height,
                selector_status=effective_status(rec),
                person_scale=(rec or {}).get("person_scale", ""),
                angle_class=(rec or {}).get("angle_class", ""),
                **result,
            )
            proposals.append(asdict(proposal))

    pack = choose_review_pack(proposals, review_size)
    save_json(run_dir / "proposals.json", {
        "schema_version": HARNESS_VERSION,
        "dataset_root": str(folder.resolve()),
        "scope": scope,
        "input_stats": input_stats,
        "analysis_max_side": ANALYSIS_MAX_SIDE,
        "count": len(proposals),
        "proposals": proposals,
    })
    write_proposals_csv(run_dir / "proposals.csv", proposals)
    save_json(run_dir / "review_pack.json", {
        "schema_version": HARNESS_VERSION,
        "dataset_root": str(folder.resolve()),
        "count": len(pack),
        "samples": pack,
    })
    save_json(run_dir / "review_labels.json", {"schema_version": HARNESS_VERSION, "labels": {}})
    write_contact_sheets(run_dir, pack)
    write_summary(run_dir)
    print(f"\n完成：{run_dir}")
    return run_dir


def load_run(run_dir: Path) -> tuple[list[dict], dict[str, str]]:
    pack = json.loads((run_dir / "review_pack.json").read_text(encoding="utf-8"))
    labels_path = run_dir / "review_labels.json"
    labels_data = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {"labels": {}}
    return list(pack.get("samples", [])), dict(labels_data.get("labels", {}))


def write_summary(run_dir: Path) -> dict:
    proposals_data = json.loads((run_dir / "proposals.json").read_text(encoding="utf-8"))
    proposals = proposals_data.get("proposals", [])
    pack, labels = load_run(run_dir) if (run_dir / "review_pack.json").exists() else ([], {})

    crop_reviewed = [p for p in pack if p["decision"] == "suggest_crop" and labels.get(p["path"])]
    keep_reviewed = [p for p in pack if p["decision"] == "keep_original" and labels.get(p["path"])]
    safe = [p for p in crop_reviewed if labels.get(p["path"]) == "SAFE"]

    summary = {
        "schema_version": HARNESS_VERSION,
        "total_proposals": len(proposals),
        "crop_suggestions": sum(p["decision"] == "suggest_crop" for p in proposals),
        "auto_suggestion_coverage": (
            sum(p["decision"] == "suggest_crop" for p in proposals) / len(proposals) if proposals else 0.0
        ),
        "review_pack_count": len(pack),
        "reviewed": sum(1 for p in pack if labels.get(p["path"])),
        "critical_content_cut_rate": (
            sum(labels.get(p["path"]) == "TOO_TIGHT" for p in crop_reviewed) / len(crop_reviewed)
            if crop_reviewed else None
        ),
        "safe_suggestion_precision": (
            len(safe) / len(crop_reviewed) if crop_reviewed else None
        ),
        "manual_adjust_rate": (
            sum(labels.get(p["path"]) == "MANUAL" for p in crop_reviewed) / len(crop_reviewed)
            if crop_reviewed else None
        ),
        "missed_crop_rate": (
            sum(labels.get(p["path"]) == "MISSED_CROP" for p in keep_reviewed) / len(keep_reviewed)
            if keep_reviewed else None
        ),
        "median_safe_trim_ratio": (
            statistics.median(p["trim_ratio"] for p in safe) if safe else None
        ),
        "label_counts": {
            name: sum(value == name for value in labels.values())
            for name, _ in CROP_LABELS + KEEP_LABELS
        },
    }
    save_json(run_dir / "summary.json", summary)
    return summary


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    arr = np.asarray(image.convert("RGB"))
    h, w = arr.shape[:2]
    q = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(q)


class PreviewLabel(QLabel):
    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.base = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(280, 300)
        self.setText(title)

    def set_preview(self, image: Image.Image):
        self.base = pil_to_pixmap(image)
        self._refresh()

    def clear_preview(self, message: str):
        self.base = QPixmap()
        self.setText(message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        if self.base.isNull():
            return
        self.setPixmap(self.base.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class ReviewWindow(QMainWindow):
    def __init__(self, run_dir: Path):
        super().__init__()
        self.run_dir = run_dir
        self.samples, self.labels = load_run(run_dir)
        self.index = self.first_unreviewed()
        self.setWindowTitle("Auto Crop Research Review")
        self.resize(1550, 900)
        self.build_ui()
        self.show_current()

    def first_unreviewed(self) -> int:
        for i, sample in enumerate(self.samples):
            if not self.labels.get(sample["path"]):
                return i
        return 0

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.progress = QLabel()
        self.info = QLabel()
        self.info.setWordWrap(True)
        top.addWidget(self.progress)
        top.addWidget(self.info, 1)
        layout.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        self.original = PreviewLabel("原图")
        self.overlay = PreviewLabel("建议裁剪框")
        self.cropped = PreviewLabel("裁后预览")
        split.addWidget(self.original)
        split.addWidget(self.overlay)
        split.addWidget(self.cropped)
        split.setSizes([500, 500, 500])
        layout.addWidget(split, 1)

        self.reason = QLabel()
        self.reason.setWordWrap(True)
        layout.addWidget(self.reason)

        nav = QHBoxLayout()
        prev_btn = QPushButton("← 上一张")
        prev_btn.clicked.connect(lambda: self.move(-1))
        next_btn = QPushButton("下一张 →")
        next_btn.clicked.connect(lambda: self.move(1))
        nav.addWidget(prev_btn)
        nav.addStretch(1)
        self.buttons = {}
        for idx, (code, text) in enumerate(CROP_LABELS + KEEP_LABELS, 1):
            btn = QPushButton(f"{idx}. {text}")
            btn.clicked.connect(lambda _=False, c=code: self.record(c))
            self.buttons[code] = btn
            nav.addWidget(btn)
        nav.addStretch(1)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        QShortcut(QKeySequence("Left"), self, activated=lambda: self.move(-1))
        QShortcut(QKeySequence("Right"), self, activated=lambda: self.move(1))
        for idx, (code, _) in enumerate(CROP_LABELS + KEEP_LABELS, 1):
            QShortcut(QKeySequence(str(idx)), self, activated=lambda c=code: self.record(c))

    def current(self) -> dict | None:
        if not self.samples:
            return None
        return self.samples[max(0, min(self.index, len(self.samples) - 1))]

    def show_current(self):
        sample = self.current()
        if not sample:
            self.progress.setText("没有 Review Pack")
            return

        self.index = max(0, min(self.index, len(self.samples) - 1))
        reviewed = sum(bool(self.labels.get(s["path"])) for s in self.samples)
        self.progress.setText(f"{self.index + 1} / {len(self.samples)}　已复核 {reviewed}")
        self.info.setText(
            f'{sample["relative_path"]}　｜　{sample["decision"]}　｜　'
            f'潜在裁减 {sample["potential_trim_ratio"]:.1%}　｜　风险 {sample["risk_level"]}'
        )
        self.reason.setText("原因：" + "；".join(sample.get("reason", [])))

        crop_mode = sample["decision"] == "suggest_crop"
        for code, _ in CROP_LABELS:
            self.buttons[code].setEnabled(crop_mode)
        for code, _ in KEEP_LABELS:
            self.buttons[code].setEnabled(not crop_mode)

        try:
            with Image.open(sample["path"]) as im:
                im.seek(0)
                image = ImageOps.exif_transpose(im).convert("RGB")
            self.original.set_preview(image)
            if sample.get("crop_box"):
                overlay = draw_crop_overlay(image, sample["crop_box"])
                x0, y0, x1, y1 = sample["crop_box"]
                cropped = image.crop((x0, y0, x1, y1))
                self.overlay.set_preview(overlay)
                self.cropped.set_preview(cropped)
            else:
                self.overlay.set_preview(image)
                self.cropped.clear_preview("KEEP ORIGINAL")
        except Exception as exc:
            self.original.clear_preview(str(exc))
            self.overlay.clear_preview("无法预览")
            self.cropped.clear_preview("无法预览")

        current_label = self.labels.get(sample["path"], "")
        if current_label:
            self.reason.setText(self.reason.text() + f"　｜　当前标注：{current_label}")

    def save_labels(self):
        save_json(self.run_dir / "review_labels.json", {
            "schema_version": HARNESS_VERSION,
            "labels": self.labels,
        })
        write_summary(self.run_dir)

    def record(self, code: str):
        sample = self.current()
        if not sample:
            return
        allowed = {c for c, _ in (CROP_LABELS if sample["decision"] == "suggest_crop" else KEEP_LABELS)}
        if code not in allowed:
            return
        self.labels[sample["path"]] = code
        self.save_labels()
        if self.index + 1 < len(self.samples):
            self.index += 1
            self.show_current()
            return

        self.show_current()
        if all(self.labels.get(s["path"]) for s in self.samples):
            summary = write_summary(self.run_dir)
            latest_summary = PROJECT_ROOT / "research" / "latest-summary.json"
            try:
                shutil.copy2(self.run_dir / "summary.json", latest_summary)
            except Exception:
                traceback.print_exc()
            def pct(v):
                return "N/A" if v is None else f"{v:.1%}"
            report = (
                f"已完成 {summary['reviewed']} / {summary['review_pack_count']} 张复核\n\n"
                f"总分析：{summary['total_proposals']}\n"
                f"裁剪建议：{summary['crop_suggestions']} "
                f"({summary['auto_suggestion_coverage']:.1%})\n"
                f"安全建议精度：{pct(summary['safe_suggestion_precision'])}\n"
                f"关键内容切断率：{pct(summary['critical_content_cut_rate'])}\n"
                f"需要手调率：{pct(summary['manual_adjust_rate'])}\n"
                f"KEEP 漏裁率：{pct(summary['missed_crop_rate'])}\n"
                f"安全裁剪中位裁减：{pct(summary['median_safe_trim_ratio'])}\n\n"
                f"报告目录：\n{self.run_dir}\n\n"
                f"便捷副本：\n{latest_summary}"
            )
            print(f"Benchmark report: {self.run_dir / 'summary.json'}", flush=True)
            print(f"Latest summary copy: {latest_summary}", flush=True)
            QMessageBox.information(self, "Auto Crop Benchmark 报告", report)

    def move(self, delta: int):
        if not self.samples:
            return
        self.index = max(0, min(len(self.samples) - 1, self.index + delta))
        self.show_current()

    def closeEvent(self, event):
        self.save_labels()
        super().closeEvent(event)


def self_test() -> None:
    image = np.zeros((320, 480, 3), np.uint8)
    image[70:280, 160:320] = 200
    sal = saliency_map(image)
    if sal.shape != image.shape[:2] or not np.isfinite(sal).all():
        raise RuntimeError("saliency self-test failed")

    hard = np.zeros((320, 480), np.uint8)
    hard[80:270, 170:310] = 255
    nearby, remote = nearby_saliency_mask(sal, hard)
    if nearby.shape != hard.shape or not math.isfinite(remote):
        raise RuntimeError("protection self-test failed")

    proposals = [
        {"path": f"crop_{i}.jpg", "decision": "suggest_crop", "trim_ratio": i / 100, "potential_trim_ratio": i / 100, "risk_score": i / 100}
        for i in range(20)
    ] + [
        {"path": f"keep_{i}.jpg", "decision": "keep_original", "trim_ratio": 0.0, "potential_trim_ratio": i / 100, "risk_score": 0.5}
        for i in range(20)
    ]
    pack = choose_review_pack(proposals, 20)
    if len(pack) != 20 or len({p["path"] for p in pack}) != 20:
        raise RuntimeError("review pack self-test failed")

    # Exercise the real bundled Pose model too; the old self-test stopped before
    # the code path used by the benchmark itself.
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ensure_pose())),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_poses=1,
        output_segmentation_masks=True,
    )
    # 127 px deliberately reproduces the upstream float-mask stride bug unless
    # our width-padding workaround is active.
    large = np.zeros((2400, 3600, 3), dtype=np.uint8)
    resized, resize_scale = resize_for_analysis(large)
    if max(resized.shape[:2]) != ANALYSIS_MAX_SIDE or not (0 < resize_scale < 1):
        raise RuntimeError("analysis downscale self-test failed")

    blank = np.zeros((128, 127, 3), dtype=np.uint8)
    with PoseLandmarker.create_from_options(options) as landmarker:
        result, pose_width, pad_right = pose_detect_padded(blank, landmarker)
        if pose_width % 4 != 0 or pad_right != 1:
            raise RuntimeError("pose width-padding self-test failed")
        if result.segmentation_masks:
            mask = np.asarray(result.segmentation_masks[0].numpy_view())
            if mask.shape[1] != pose_width:
                raise RuntimeError("segmentation mask width self-test failed")

    print("Auto Crop research harness self-test OK")


def parse_args():
    parser = argparse.ArgumentParser(description="Auto Crop research harness v0")
    parser.add_argument("folder", nargs="?", help="dataset folder")
    parser.add_argument("--all", action="store_true", help="analyze all images instead of selector recommendations")
    parser.add_argument("--review-size", type=int, default=REVIEW_SIZE_DEFAULT)
    parser.add_argument("--review", type=str, help="open an existing run directory")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    app = QApplication.instance() or QApplication(sys.argv)

    if args.review:
        run_dir = Path(args.review)
    else:
        folder = Path(args.folder) if args.folder else None
        if not folder:
            sibling_valby = PROJECT_ROOT.parent / "渥尔比"
            if sibling_valby.exists():
                folder = sibling_valby
            else:
                selected = QFileDialog.getExistingDirectory(None, "选择 Valby / 角色图片文件夹")
                if not selected:
                    return 0
                folder = Path(selected)
        print(f"Dataset folder: {folder}", flush=True)
        if not folder.exists():
            print(f"ERROR: dataset folder does not exist: {folder}", file=sys.stderr, flush=True)
            QMessageBox.critical(None, "目录不存在", str(folder))
            return 2
        dialog = QProgressDialog("准备分析…", "取消", 0, 100)
        dialog.setWindowTitle("Auto Crop Research")
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        app.processEvents()

        def update_progress(index, total, name):
            if dialog.wasCanceled():
                raise RuntimeError("用户取消分析")
            dialog.setMaximum(max(1, total))
            dialog.setValue(max(0, index - 1))
            dialog.setLabelText(f"正在分析 {index} / {total}\n{name}")
            app.processEvents()

        try:
            run_dir = analyze(folder, args.all, args.review_size, update_progress)
            dialog.setValue(dialog.maximum())
            dialog.setLabelText("分析完成，正在打开复核界面…")
            app.processEvents()
        except Exception as exc:
            dialog.close()
            print("Auto Crop benchmark failed:", file=sys.stderr, flush=True)
            traceback.print_exc()
            QMessageBox.critical(None, "Auto Crop benchmark 失败", str(exc))
            return 2
        finally:
            dialog.close()

    window = ReviewWindow(run_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
