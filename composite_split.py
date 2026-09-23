"""Production Composite Split adapter.

The visual detectors reuse the mature DeepGHS person/head models and the
vendored, parity-tested DeepGHS YOLO inference path. This module only maps
their outputs to selector-specific proposals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

PERSON_MODEL = "person_detect_v1.3_s"
HEAD_MODEL = "head_detect_v2.0_s"
PERSON_CONF = 0.30
PERSON_IOU = 0.50
HEAD_CONF = 0.40

MIN_IMAGE_AREA_RATIO = 0.03
MIN_LARGEST_AREA_RATIO = 0.20
DUPLICATE_SMALLER_COVERAGE = 0.78
MAX_RAW_DETECTIONS = 8
MAX_SPLITS = 6
GROUP_OVERLAP_SMALLER_COVERAGE = 0.18
GROUP_MARGIN_RATIO = 0.08
PROPOSAL_VERSION = 2


@dataclass
class Detection:
    bbox: list[int] = field(default_factory=list)
    confidence: float = 0.0
    kind: str = "person"


@dataclass
class CompositeProposal:
    version: int = PROPOSAL_VERSION
    mode: str = ""  # split_people | group_crop
    output_boxes: list[list[int]] = field(default_factory=list)
    person_detections: list[Detection] = field(default_factory=list)
    head_detections: list[Detection] = field(default_factory=list)
    decision: str = "pending"  # pending | accepted | rejected
    detail: str = ""


def proposal_to_dict(value: Optional[CompositeProposal]):
    return asdict(value) if value is not None else None


def proposal_from_dict(value) -> Optional[CompositeProposal]:
    if isinstance(value, CompositeProposal) or value is None:
        return value
    if not isinstance(value, dict):
        return None
    try:
        return CompositeProposal(
            version=int(value.get("version", PROPOSAL_VERSION)),
            mode=str(value.get("mode", "")),
            output_boxes=[list(map(int, b)) for b in value.get("output_boxes", [])],
            person_detections=[
                Detection(
                    bbox=list(map(int, d.get("bbox", []))),
                    confidence=float(d.get("confidence", 0.0)),
                    kind=str(d.get("kind", "person")),
                )
                for d in value.get("person_detections", [])
                if isinstance(d, dict)
            ],
            head_detections=[
                Detection(
                    bbox=list(map(int, d.get("bbox", []))),
                    confidence=float(d.get("confidence", 0.0)),
                    kind=str(d.get("kind", "head")),
                )
                for d in value.get("head_detections", [])
                if isinstance(d, dict)
            ],
            decision=str(value.get("decision", "pending")),
            detail=str(value.get("detail", "")),
        )
    except Exception:
        return None


def _area(box) -> int:
    x0, y0, x1, y1 = box
    return max(0, x1 - x0) * max(0, y1 - y0)


def _intersection(a, b) -> int:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    x0, y0 = max(ax0, bx0), max(ay0, by0)
    x1, y1 = min(ax1, bx1), min(ay1, by1)
    return max(0, x1 - x0) * max(0, y1 - y0)


def _center(box):
    x0, y0, x1, y1 = box
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _contains(box, point) -> bool:
    x0, y0, x1, y1 = box
    x, y = point
    return x0 <= x <= x1 and y0 <= y <= y1


def _suppress_nested(detections):
    ordered = sorted(detections, key=lambda d: (_area(d.bbox), d.confidence), reverse=True)
    kept = []
    for detection in ordered:
        duplicate = False
        for previous in kept:
            inter = _intersection(detection.bbox, previous.bbox)
            smaller = max(1, min(_area(detection.bbox), _area(previous.bbox)))
            if inter / smaller >= DUPLICATE_SMALLER_COVERAGE:
                duplicate = True
                break
        if not duplicate:
            kept.append(detection)
    return kept


def _significant(detections, image_size):
    if not detections:
        return []
    width, height = image_size
    image_area = max(1, width * height)
    largest = max(_area(d.bbox) for d in detections)
    return [
        d
        for d in detections
        if _area(d.bbox) / image_area >= MIN_IMAGE_AREA_RATIO
        and _area(d.bbox) / max(1, largest) >= MIN_LARGEST_AREA_RATIO
    ]


def _single_head_dedup(people, heads):
    if len(heads) != 1:
        return people
    point = _center(heads[0].bbox)
    matching = [p for p in people if _contains(p.bbox, point)]
    if len(matching) <= 1:
        return people
    best = max(matching, key=lambda d: (_area(d.bbox), d.confidence))
    ids = {id(d) for d in matching}
    return [d for d in people if id(d) not in ids] + [best]


def _is_group(people, heads) -> bool:
    if len(people) < 2 or len(heads) < 2:
        return False
    for index, left in enumerate(people):
        for right in people[index + 1 :]:
            inter = _intersection(left.bbox, right.bbox)
            smaller = max(1, min(_area(left.bbox), _area(right.bbox)))
            if inter / smaller >= GROUP_OVERLAP_SMALLER_COVERAGE:
                return True
    return False


def _union(boxes):
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def _expand(box, image_size, ratio):
    x0, y0, x1, y1 = box
    width, height = image_size
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    mx, my = round(bw * ratio), round(bh * ratio)
    return [
        max(0, x0 - mx),
        max(0, y0 - my),
        min(width, x1 + mx),
        min(height, y1 + my),
    ]


def _reading_order(people):
    if len(people) <= 1:
        return people
    centers = [(*_center(d.bbox), d) for d in people]
    xs = [x for x, _, _ in centers]
    ys = [y for _, y, _ in centers]
    if max(xs) - min(xs) >= max(ys) - min(ys):
        centers.sort(key=lambda item: (item[0], item[1]))
    else:
        centers.sort(key=lambda item: (item[1], item[0]))
    return [d for _, _, d in centers]


def proposal_from_detections(image_size, people, heads) -> Optional[CompositeProposal]:
    people = [
        d if isinstance(d, Detection) else Detection(list(map(int, d[0])), float(d[2]), str(d[1]))
        for d in people
    ]
    heads = [
        d if isinstance(d, Detection) else Detection(list(map(int, d[0])), float(d[2]), str(d[1]))
        for d in heads
    ]

    if len(people) > MAX_RAW_DETECTIONS:
        return None

    people = _significant(_suppress_nested(people), image_size)
    if not (2 <= len(people) <= MAX_SPLITS):
        return None

    if not heads:
        return None

    people = _single_head_dedup(people, heads)
    if len(people) < 2:
        return None

    if _is_group(people, heads):
        output_boxes = [_expand(_union([p.bbox for p in people]), image_size, GROUP_MARGIN_RATIO)]
        mode = "group_crop"
        detail = f"重叠多人构图：{len(people)} 人合并为 1 张群组裁剪"
    else:
        ordered = _reading_order(people)
        output_boxes = [list(p.bbox) for p in ordered]
        people = ordered
        mode = "split_people"
        detail = f"独立人物/视角：建议拆分为 {len(output_boxes)} 张"

    return CompositeProposal(
        mode=mode,
        output_boxes=output_boxes,
        person_detections=people,
        head_detections=heads,
        detail=detail,
    )


def detect_proposal(image: Image.Image, model_cache: Path) -> Optional[CompositeProposal]:
    from deepghs_yolo_runtime import detect_heads, detect_person

    people = detect_person(
        image,
        model_cache=model_cache,
        model_name=PERSON_MODEL,
        conf_threshold=PERSON_CONF,
        iou_threshold=PERSON_IOU,
    )
    if len(people) < 2 or len(people) > MAX_RAW_DETECTIONS:
        return None

    heads = detect_heads(
        image,
        model_cache=model_cache,
        model_name=HEAD_MODEL,
        conf_threshold=HEAD_CONF,
    )
    return proposal_from_detections(image.size, people, heads)
