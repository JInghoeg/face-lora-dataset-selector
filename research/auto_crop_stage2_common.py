"""Shared harness utilities for Auto Crop Stage 2.

This module freezes the exact prior human-review challenge set and provides
review-only visualization helpers. It does not derive or recommend crop boxes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw

TARGET = 20
FAILURE_LABELS = {"MISSED_CROP", "MANUAL", "TOO_TIGHT"}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESEARCH_ROOT = PROJECT_ROOT / "_research_output" / "auto_crop_stage2"


def research_root() -> Path:
    root = Path(os.environ.get("FACE_LORA_RESEARCH_ROOT", DEFAULT_RESEARCH_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def legacy_research_root() -> Path:
    override = os.environ.get("FACE_LORA_LEGACY_RESEARCH_ROOT")
    if override:
        return Path(override).resolve()
    local = Path(
        os.environ.get("LOCALAPPDATA")
        or (Path.home() / "AppData" / "Local")
    )
    return local / "Face LoRA Dataset Selector" / "research"


def legacy_review_root() -> Path:
    override = os.environ.get("FACE_LORA_LEGACY_REVIEW_ROOT")
    if override:
        return Path(override).resolve()
    return legacy_research_root() / "auto_crop"


def find_latest_stage1_result():
    root = legacy_research_root() / "mature_person_v1_3_s"
    candidates = list(root.rglob("results.json")) if root.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_stage1_challenge(result_path: Path, limit: int) -> list[tuple[Path, str]]:
    data = json.loads(result_path.read_text(encoding="utf-8"))
    samples = [
        (Path(item["path"]), str(item.get("old_label", "")))
        for item in data.get("samples", [])
        if isinstance(item, dict) and item.get("path")
    ]
    if len(samples) != limit:
        raise RuntimeError(
            f"Stage 1 results 中有 {len(samples)} 个样本，要求固定 {limit} 个。"
        )
    missing = [str(path) for path, _ in samples if not path.exists()]
    if missing:
        raise RuntimeError(
            "Stage 1 challenge 文件缺失：\n" + "\n".join(missing)
        )
    return samples


def find_latest_review_run() -> Path:
    root = legacy_review_root()
    candidates = []
    if root.exists():
        for labels in root.rglob("review_labels.json"):
            run = labels.parent
            if (run / "review_pack.json").exists():
                candidates.append(run)
    if not candidates:
        raise RuntimeError(
            "没有找到之前完成的 Auto Crop review 结果。"
            "可用 FACE_LORA_LEGACY_REVIEW_ROOT 指定旧 review 根目录。"
        )
    return max(
        candidates,
        key=lambda path: (path / "review_labels.json").stat().st_mtime,
    )


def _select_challenge(run: Path, limit: int) -> list[tuple[Path, str]]:
    pack = json.loads(
        (run / "review_pack.json").read_text(encoding="utf-8")
    )
    labels = json.loads(
        (run / "review_labels.json").read_text(encoding="utf-8")
    ).get("labels", {})

    selected = []
    for sample in pack.get("samples", []):
        path = Path(sample["path"])
        label = labels.get(sample["path"], "")
        if label in FAILURE_LABELS and path.exists():
            selected.append((path, label))

    def priority(item):
        path, label = item
        first = 0 if label in {"MANUAL", "TOO_TIGHT"} else 1
        stable = hashlib.sha256(
            str(path).encode("utf-8")
        ).hexdigest()
        return first, stable

    selected.sort(key=priority)
    if not selected:
        raise RuntimeError(
            "Review 中没有找到 MISSED_CROP / MANUAL / TOO_TIGHT 样本。"
        )
    return selected[:limit]


def freeze_or_load_challenge(
    limit: int = TARGET,
    refresh: bool = False,
) -> tuple[Path, list[tuple[Path, str]]]:
    root = research_root()
    manifest = root / "challenge_manifest.json"

    if manifest.exists() and not refresh:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        samples = [
            (Path(item["path"]), str(item["old_label"]))
            for item in data.get("samples", [])
        ]
        if len(samples) != limit:
            raise RuntimeError(
                f"已冻结 challenge 数量为 {len(samples)}，"
                f"当前要求 {limit}。不要静默更换测试集；"
                "确需重建时显式使用 --refresh-challenge。"
            )
        missing = [str(path) for path, _ in samples if not path.exists()]
        if missing:
            raise RuntimeError(
                "已冻结的 challenge 文件缺失：\n" + "\n".join(missing)
            )
        return manifest, samples

    stage1_result = find_latest_stage1_result()
    if stage1_result is not None:
        samples = load_stage1_challenge(stage1_result, limit)
        source = {
            "kind": "stage1_results",
            "path": str(stage1_result),
        }
        selection_rule = [
            "reuse exact Stage 1 executed challenge order",
        ]
    else:
        run = find_latest_review_run()
        samples = _select_challenge(run, limit)
        if len(samples) != limit:
            raise RuntimeError(
                f"只找到 {len(samples)} 个失败样本，要求固定 {limit} 个。"
            )
        source = {
            "kind": "legacy_review",
            "path": str(run),
        }
        selection_rule = [
            "MANUAL and TOO_TIGHT first",
            "then MISSED_CROP",
            "stable SHA-256 path ordering",
        ]

    payload = {
        "schema_version": 1,
        "source": source,
        "selection_rule": selection_rule,
        "count": len(samples),
        "samples": [
            {"path": str(path), "old_label": label}
            for path, label in samples
        ],
    }
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest, samples


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB").copy()
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(
        image,
        (
            (size[0] - image.width) // 2,
            (size[1] - image.height) // 2,
        ),
    )
    return canvas


def overlay_boxes(image: Image.Image, detections) -> Image.Image:
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    width = max(3, round(min(out.size) * 0.006))
    for index, (box, kind, score) in enumerate(detections, 1):
        x0, y0, x1, y1 = box
        draw.rectangle(
            (x0, y0, x1 - 1, y1 - 1),
            outline="red",
            width=width,
        )
        draw.text(
            (x0 + 4, max(0, y0 - 16)),
            f"{index}:{kind} {score:.3f}",
            fill="red",
        )
    return out


def box_area(box) -> int:
    x0, y0, x1, y1 = box
    return max(0, x1 - x0) * max(0, y1 - y0)


def primary_detection(detections):
    """Review-only dominant-person display policy.

    This is not a production crop rule.
    """
    if not detections:
        return None, False
    ordered = sorted(
        detections,
        key=lambda item: box_area(item[0]),
        reverse=True,
    )
    primary = ordered[0]
    ambiguous = False
    if len(ordered) > 1:
        largest = max(1, box_area(primary[0]))
        second = box_area(ordered[1][0])
        ambiguous = (second / largest) >= 0.60
    return primary, ambiguous
