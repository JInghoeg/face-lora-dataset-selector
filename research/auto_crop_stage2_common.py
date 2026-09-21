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

STAGE1_EXECUTED_FILENAMES = (
    "Screenshot_2026-09-20_01-52-38.png",
    "1aaimb6xitze1.jpeg",
    "i-cant-get-enough-of-valby-v0-jno2ysaxo8zg1.webp",
    "Screenshot_2026-09-20_01-53-24.png",
    "下载 (14).jpg",
    "TheFirstDescendant_Cosmetics04.png",
    "Screenshot_2026-09-20_01-53-52.png",
    "VALBY 1.png",
    "下载 (8).jpg",
    "bax-belbi-02.webp",
    "valby-on-top-v0-i60whghu45dh1.webp",
    "9160f30c-8db3-4cac-8fff-95bc29342910.png",
    "下载 (7).jpg",
    "下载 (5).jpg",
    "Screenshot_2026-09-20_01-55-35.png",
    "Screenshot_2026-09-20_01-52-59.png",
    "下载 (31).jpg",
    "下载 (6).jpg",
    "Screenshot_2026-08-23_04-37-26.webp",
    "360807_10_webp_The First Descendant   2024-09-07 오후 10_57_15.webp",
)

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


def dataset_root() -> Path:
    override = os.environ.get("FACE_LORA_DATASET_ROOT")
    if override:
        root = Path(override).resolve()
        if root.exists():
            return root
    known = Path(r"G:\ComfyUI-aki\数据集\渥尔比")
    if known.exists():
        return known
    raise RuntimeError(
        "找不到当前 Valby 数据集。"
        "可用 FACE_LORA_DATASET_ROOT 指定数据集根目录。"
    )


def recover_stage1_challenge_by_filename(limit: int):
    if limit != len(STAGE1_EXECUTED_FILENAMES):
        raise RuntimeError(
            f"Stage 1 已执行 challenge 固定为 "
            f"{len(STAGE1_EXECUTED_FILENAMES)} 张，当前要求 {limit} 张。"
        )
    root = dataset_root()
    by_name = {}
    for path in root.rglob("*"):
        if path.is_file() and path.name in STAGE1_EXECUTED_FILENAMES:
            by_name.setdefault(path.name, []).append(path)

    missing = [
        name for name in STAGE1_EXECUTED_FILENAMES
        if name not in by_name
    ]
    ambiguous = {
        name: paths for name, paths in by_name.items()
        if len(paths) > 1
    }
    if missing:
        raise RuntimeError(
            "无法从当前数据集恢复 Stage 1 challenge，缺少文件：\n"
            + "\n".join(missing)
        )
    if ambiguous:
        details = []
        for name, paths in ambiguous.items():
            details.append(name)
            details.extend(f"  - {path}" for path in paths)
        raise RuntimeError(
            "Stage 1 challenge 文件名在当前数据集中不唯一，"
            "不能静默猜测：\n" + "\n".join(details)
        )

    return [
        (by_name[name][0], "STAGE1_REPLAY")
        for name in STAGE1_EXECUTED_FILENAMES
    ]


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
        try:
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
        except RuntimeError:
            samples = recover_stage1_challenge_by_filename(limit)
            source = {
                "kind": "stage1_executed_filename_recovery",
                "path": str(dataset_root()),
            }
            selection_rule = [
                "recover exact Stage 1 executed filenames in original order",
                "require every filename to resolve uniquely",
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
