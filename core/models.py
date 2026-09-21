"""Core domain records shared by backend features and presentation adapters.

This module intentionally contains data only. No Qt, filesystem mutation,
model runtime, or feature implementation imports are allowed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AnalysisFinding:
    code: str
    source: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    detail: Optional[str] = None


@dataclass
class FaceDetection:
    detection_id: str
    bbox_xywh: list[float] = field(default_factory=list)
    confidence: float = 0.0
    area_ratio: float = 0.0
    face_px: int = 0
    is_primary: bool = False
    detector: str = "yunet"


@dataclass
class AISuggestion:
    patch_id: str = ""
    bundle_id: str = ""
    suggested_eligibility: Optional[str] = None
    suggested_status: Optional[str] = None
    flags: list[str] = field(default_factory=list)
    note: str = ""
    request_full_resolution: bool = False
    decision: str = "pending"


@dataclass
class ViewSpec:
    name: str = ""
    filters: dict = field(default_factory=dict)
    sort_field: str = "默认顺序"
    sort_direction: str = "优先顺序"
    best_only: bool = False
    quick_mode: str = ""
    limit_n: int = 10
    ranking_basis: str = "综合质量"


@dataclass
class Photo:
    path: Path
    file_size: int = 0
    mtime_ns: int = 0
    width: int = 0
    height: int = 0
    sample_id: str = ""
    content_sha256: str = ""
    faces: int = 0
    face_detections: list[FaceDetection] = field(default_factory=list)
    primary_face_id: Optional[str] = None
    face_ratio: float = 0.0
    face_px: int = 0
    blur: float = 0.0
    brightness: float = 0.0
    face_quality: float = 0.0
    brisque: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    angle_class: str = "未检测"
    pitch_class: str = "未检测"
    person_scale: str = "未检测身体"
    phash: int = 0
    duplicate_group: int = 0
    duplicate_ignore: bool = False
    duplicate_reviewed: bool = False
    analysis_metrics: dict = field(default_factory=dict)
    review_flags: list[AnalysisFinding] = field(default_factory=list)
    hard_rejects: list[AnalysisFinding] = field(default_factory=list)
    eligibility: str = "REVIEW"
    recommendation_reasons: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    auto_status: str = "备选"
    manual_status: Optional[str] = None
    ai_suggestion: Optional[AISuggestion] = None
    composite_proposal: Optional[object] = None
    composite_scan_version: int = 0

    @property
    def status(self):
        return self.manual_status or self.auto_status

    @property
    def source(self):
        if "_frame_" in self.path.stem:
            return self.path.stem.split("_frame_", 1)[0]
        return str(self.path.parent.resolve())


@dataclass
class TextPhoto:
    path: Path
    file_size: int
    mtime_ns: int
    boxes: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    manual: list = field(default_factory=list)
    scores: list = field(default_factory=list)
    suggested: list = field(default_factory=list)
    width: int = 0
    height: int = 0


def view_field_value(photo: Photo, field_name: str):
    aliases = {
        "status": lambda r: r.status,
        "person_scale": lambda r: r.person_scale,
        "angle_class": lambda r: r.angle_class,
        "pitch_class": lambda r: r.pitch_class,
        "eligibility": lambda r: r.eligibility,
        "duplicate_group": lambda r: r.duplicate_group,
        "source": lambda r: r.source,
        "face_quality": lambda r: r.face_quality,
        "brisque": lambda r: r.brisque,
        "blur": lambda r: r.blur,
        "face_px": lambda r: r.face_px,
    }
    fn = aliases.get(field_name)
    return fn(photo) if fn else getattr(photo, field_name, None)


def photo_matches_filters(photo: Photo, filters: dict) -> bool:
    return all(
        view_field_value(photo, field_name) == expected
        for field_name, expected in filters.items()
    )


def derive_eligibility(photo: Photo):
    photo.eligibility = (
        "REJECT"
        if photo.hard_rejects
        else ("REVIEW" if photo.review_flags else "PASS")
    )
    return photo.eligibility
