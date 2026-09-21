"""General Auto Crop backend.

This module owns product policy for:
- which current 推荐 images need an Auto Crop scan;
- converting a validated ISNetIS soft mask into a conservative crop proposal;
- persisting human Accept / Keep Original decisions in generic feature_state.

No Qt/UI imports and no source-image mutation.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageOps

from .runtime import get_isnetis_mask


FEATURE_KEY = "auto_crop"
PROPOSAL_VERSION = 1

PRIMARY_ALPHA_MIN = 0.10
FIXED_PADDING_PX = 32

# Initial no-op filter only. This does NOT auto-accept any crop.
MIN_REMOVED_AREA_RATIO = 0.05


@dataclass
class AutoCropProposal:
    version: int = PROPOSAL_VERSION
    box: list[int] = field(default_factory=list)
    decision: str = "pending"
    removed_area_ratio: float = 0.0
    alpha_min: float = PRIMARY_ALPHA_MIN
    padding_px: int = FIXED_PADDING_PX
    mask_touches_edge: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class AutoCropScanResult:
    scanned: int = 0
    candidates: int = 0
    no_candidate: int = 0
    skipped_existing: int = 0


def proposal_from_dict(value) -> Optional[AutoCropProposal]:
    if isinstance(value, AutoCropProposal):
        return value
    if not isinstance(value, dict):
        return None
    if int(value.get("version", 0)) != PROPOSAL_VERSION:
        return None
    try:
        proposal = AutoCropProposal(**value)
    except TypeError:
        return None
    if proposal.decision not in ("pending", "accepted", "keep_original"):
        return None
    if len(proposal.box) != 4:
        return None
    return proposal


def _state(photo):
    value = photo.feature_state.get(FEATURE_KEY)
    return value if isinstance(value, dict) else None


def current_proposal(photo) -> Optional[AutoCropProposal]:
    state = _state(photo)
    if not state or int(state.get("version", 0)) != PROPOSAL_VERSION:
        return None
    return proposal_from_dict(state.get("proposal"))


def _write_state(photo, proposal=None, state_kind="scanned"):
    photo.feature_state[FEATURE_KEY] = {
        "version": PROPOSAL_VERSION,
        "state": state_kind,
        "proposal": proposal.to_dict() if proposal is not None else None,
    }


def _threshold_bbox(mask: np.ndarray, alpha_min: float):
    support = np.asarray(mask) >= float(alpha_min)
    ys, xs = np.nonzero(support)
    if not len(xs):
        return None
    return (
        int(xs.min()),
        int(ys.min()),
        int(xs.max()) + 1,
        int(ys.max()) + 1,
    )


def _expand_box(box, image_size, padding_px):
    width, height = image_size
    x0, y0, x1, y1 = map(int, box)
    p = max(0, int(padding_px))
    return [
        max(0, x0 - p),
        max(0, y0 - p),
        min(width, x1 + p),
        min(height, y1 + p),
    ]


def _removed_area_ratio(box, image_size):
    width, height = image_size
    total = max(1, width * height)
    x0, y0, x1, y1 = box
    kept = max(0, x1 - x0) * max(0, y1 - y0)
    return max(0.0, min(1.0, 1.0 - kept / total))


def proposal_from_mask(
    mask: np.ndarray,
    image_size,
    *,
    alpha_min: float = PRIMARY_ALPHA_MIN,
    padding_px: int = FIXED_PADDING_PX,
    min_removed_area_ratio: float = MIN_REMOVED_AREA_RATIO,
):
    raw = _threshold_bbox(mask, alpha_min)
    if raw is None:
        return None

    width, height = image_size
    touches = (
        raw[0] <= 0
        or raw[1] <= 0
        or raw[2] >= width
        or raw[3] >= height
    )
    box = _expand_box(raw, image_size, padding_px)
    removed = _removed_area_ratio(box, image_size)

    # Near-no-op proposals do not consume human review time.
    if removed < float(min_removed_area_ratio):
        return None

    warnings = []
    if touches:
        warnings.append("subject_mask_touches_source_edge")
    return AutoCropProposal(
        box=box,
        removed_area_ratio=removed,
        alpha_min=float(alpha_min),
        padding_px=int(padding_px),
        mask_touches_edge=touches,
        warnings=warnings,
    )


def detect_proposal(
    path: Path,
    model_cache: Path,
    *,
    alpha_min: float = PRIMARY_ALPHA_MIN,
    padding_px: int = FIXED_PADDING_PX,
    min_removed_area_ratio: float = MIN_REMOVED_AREA_RATIO,
):
    with Image.open(path) as source:
        try:
            source.seek(0)
        except EOFError:
            pass
        image = ImageOps.exif_transpose(source).convert("RGB")

    mask = get_isnetis_mask(image, model_cache)
    return proposal_from_mask(
        mask,
        image.size,
        alpha_min=alpha_min,
        padding_px=padding_px,
        min_removed_area_ratio=min_removed_area_ratio,
    )


def scan_records(records, model_cache: Path, progress=None, force=False):
    progress = progress or (lambda _current, _total, _name: None)
    targets = [record for record in records if record.status == "推荐"]
    result = AutoCropScanResult()

    for index, record in enumerate(targets, 1):
        state = _state(record)
        if (
            not force
            and state
            and int(state.get("version", 0)) == PROPOSAL_VERSION
        ):
            result.skipped_existing += 1
            progress(index, len(targets), record.path.name)
            continue

        proposal = detect_proposal(record.path, model_cache)
        result.scanned += 1
        if proposal is None:
            _write_state(record, None, state_kind="no_candidate")
            result.no_candidate += 1
        else:
            _write_state(record, proposal, state_kind="candidate")
            result.candidates += 1
        progress(index, len(targets), record.path.name)

    return result


def pending_records(records):
    output = []
    for record in records:
        if record.status != "推荐":
            continue
        proposal = current_proposal(record)
        if proposal is not None and proposal.decision == "pending":
            output.append(record)
    return output


def accept_proposal(photo):
    proposal = current_proposal(photo)
    if proposal is None:
        raise ValueError("No current Auto Crop proposal.")
    proposal.decision = "accepted"
    _write_state(photo, proposal, state_kind="candidate")
    return proposal


def keep_original(photo):
    proposal = current_proposal(photo)
    if proposal is None:
        # Explicit keep is still persisted so a rescan does not immediately
        # recreate a candidate unless the user resets/forces scan.
        photo.feature_state[FEATURE_KEY] = {
            "version": PROPOSAL_VERSION,
            "state": "keep_original",
            "proposal": None,
        }
        return None
    proposal.decision = "keep_original"
    _write_state(photo, proposal, state_kind="candidate")
    return proposal


def reset_decision(photo):
    photo.feature_state.pop(FEATURE_KEY, None)


def accepted_box(photo):
    proposal = current_proposal(photo)
    if proposal is None or proposal.decision != "accepted":
        return None
    return list(map(int, proposal.box))


def self_test():
    mask = np.full((80, 100), 0.02, dtype=np.float32)
    mask[10:60, 20:70] = 0.95

    proposal = proposal_from_mask(
        mask,
        (100, 80),
        alpha_min=0.10,
        padding_px=8,
        min_removed_area_ratio=0.0,
    )
    if proposal is None or proposal.box != [12, 2, 78, 68]:
        raise RuntimeError(f"Auto Crop geometry self-test failed: {proposal}")

    # Low alpha noise must not expand the candidate to the full frame.
    if proposal.removed_area_ratio <= 0.40:
        raise RuntimeError("Auto Crop alpha-floor self-test failed.")

    # Near-no-op filter must suppress review noise.
    near_full = np.ones((80, 100), dtype=np.float32)
    if proposal_from_mask(near_full, (100, 80), min_removed_area_ratio=0.05):
        raise RuntimeError("Auto Crop no-op filter self-test failed.")

    restored = proposal_from_dict(proposal.to_dict())
    if restored is None or restored.box != proposal.box:
        raise RuntimeError("Auto Crop proposal persistence self-test failed.")

    print("Auto Crop backend self-test OK")
