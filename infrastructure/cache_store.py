"""Dataset cache/persistence adapter.

Owns the on-disk cache schema and backward-compatible record serialization.
Feature-specific proposal decoding is injected by the application boundary.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from core.models import (
    AISuggestion,
    AnalysisFinding,
    FaceDetection,
    Photo,
    ViewSpec,
)


class DatasetCache:
    def __init__(
        self,
        cache_root: Path,
        legacy_cache_root: Path,
        analysis_version: int,
        proposal_loader=None,
        proposal_version_getter=None,
    ):
        self.cache_root = Path(cache_root)
        self.legacy_cache_root = Path(legacy_cache_root)
        self.analysis_version = int(analysis_version)
        self.proposal_loader = proposal_loader or (lambda value: None)
        self.proposal_version_getter = proposal_version_getter or (lambda: 0)

    @staticmethod
    def key(path: Path) -> str:
        return str(path.resolve()).casefold()

    def migrate_legacy(self):
        if not self.legacy_cache_root.exists():
            return
        self.cache_root.mkdir(parents=True, exist_ok=True)
        for src in self.legacy_cache_root.glob("*.json"):
            dst = self.cache_root / src.name
            if not dst.exists():
                try:
                    shutil.copy2(src, dst)
                except OSError:
                    pass
        legacy_thumbs = self.legacy_cache_root / "thumbnails"
        thumb_cache = self.cache_root / "thumbnails"
        if legacy_thumbs.exists() and not thumb_cache.exists():
            try:
                shutil.copytree(legacy_thumbs, thumb_cache)
            except OSError:
                pass

    def cache_path(self, folder: Path) -> Path:
        digest = hashlib.sha256(self.key(folder).encode()).hexdigest()[:24]
        return self.cache_root / f"{digest}.json"

    def load_data(self, folder: Path):
        try:
            data = json.loads(self.cache_path(folder).read_text(encoding="utf-8"))
            version = data.get("version", data.get("schema_version"))
            return data if version in (1, 2, 3) else {}
        except Exception:
            return {}

    def load_cached(self, folder: Path):
        data = self.load_data(folder)
        if (
            data.get("version", data.get("schema_version")) != 3
            or data.get("analysis_version") != self.analysis_version
        ):
            return {}
        return {
            item["path"].casefold(): item
            for item in data.get("records", [])
            if isinstance(item, dict) and item.get("path")
        }

    def load_cached_by_hash(self, folder: Path):
        data = self.load_data(folder)
        if (
            data.get("version", data.get("schema_version")) != 3
            or data.get("analysis_version") != self.analysis_version
        ):
            return {}
        out = defaultdict(list)
        for item in data.get("records", []):
            if isinstance(item, dict) and item.get("content_sha256"):
                out[item["content_sha256"]].append(item)
        return out

    def historical_records(self, folder: Path):
        data = self.load_data(folder)
        return {
            str(item.get("path", "")).casefold(): item
            for item in data.get("records", [])
            if isinstance(item, dict) and item.get("path")
        }

    def legacy_manual_states(self, folder: Path):
        data = self.load_data(folder)
        if data.get("version", data.get("schema_version")) not in (1, 2):
            return {}
        return {
            item["path"].casefold(): item.get("manual_status")
            for item in data.get("records", [])
            if isinstance(item, dict)
            and item.get("path")
            and item.get("manual_status")
        }

    @staticmethod
    def _finding_from_dict(value):
        if isinstance(value, AnalysisFinding):
            return value
        if isinstance(value, dict):
            return AnalysisFinding(**value)
        return AnalysisFinding(str(value), "legacy", detail=str(value))

    @staticmethod
    def _face_detection_from_dict(value):
        if isinstance(value, FaceDetection):
            return value
        return FaceDetection(**value) if isinstance(value, dict) else None

    @staticmethod
    def _ai_suggestion_from_dict(value):
        if isinstance(value, AISuggestion) or value is None:
            return value
        return AISuggestion(**value) if isinstance(value, dict) else None

    def ai_suggestion_from_dict(self, value):
        return self._ai_suggestion_from_dict(value)

    @staticmethod
    def photo_to_dict(photo: Photo):
        data = asdict(photo)
        data["path"] = str(photo.path.resolve())
        return data

    def photo_from_dict(self, data, path: Path, size: int, mtime: int):
        photo = Photo(path, size, mtime)
        simple = (
            "width",
            "height",
            "sample_id",
            "content_sha256",
            "faces",
            "primary_face_id",
            "face_ratio",
            "face_px",
            "blur",
            "brightness",
            "face_quality",
            "brisque",
            "yaw",
            "pitch",
            "roll",
            "angle_class",
            "pitch_class",
            "person_scale",
            "phash",
            "duplicate_group",
            "duplicate_ignore",
            "duplicate_reviewed",
            "analysis_metrics",
            "eligibility",
            "auto_status",
            "manual_status",
            "composite_scan_version",
            "feature_state",
        )
        for name in simple:
            if name in data:
                setattr(photo, name, data[name])

        photo.face_detections = [
            item
            for item in (
                self._face_detection_from_dict(value)
                for value in data.get("face_detections", [])
            )
            if item is not None
        ]
        photo.review_flags = [
            self._finding_from_dict(value)
            for value in data.get("review_flags", [])
        ]
        photo.hard_rejects = [
            self._finding_from_dict(value)
            for value in data.get("hard_rejects", [])
        ]
        photo.recommendation_reasons = list(data.get("recommendation_reasons", []))
        photo.reasons = list(data.get("reasons", []))
        photo.ai_suggestion = self._ai_suggestion_from_dict(
            data.get("ai_suggestion")
        )

        proposal = self.proposal_loader(data.get("composite_proposal"))
        proposal_version = int(self.proposal_version_getter())
        if (
            proposal is not None
            and getattr(proposal, "version", None) == proposal_version
        ):
            photo.composite_proposal = proposal
        else:
            photo.composite_proposal = None
            if proposal is not None:
                photo.composite_scan_version = 0
        return photo

    @staticmethod
    def view_spec_from_dict(value):
        if isinstance(value, ViewSpec):
            return value
        if not isinstance(value, dict):
            return ViewSpec()

        field_name = str(value.get("sort_field", "默认顺序"))
        direction = str(value.get("sort_direction", "优先顺序"))
        legacy = str(value.get("sort_mode", ""))
        legacy_map = {
            "Face Quality 高 → 低": ("Face Quality", "优先顺序"),
            "Face Quality 低 → 高": ("Face Quality", "反向"),
            "BRISQUE 低 → 高": ("BRISQUE", "优先顺序"),
            "BRISQUE 高 → 低": ("BRISQUE", "反向"),
            "Sharpness 高 → 低": ("Sharpness", "优先顺序"),
            "Sharpness 低 → 高": ("Sharpness", "反向"),
            "状态": ("状态", "优先顺序"),
            "Duplicate Group": ("Duplicate Group", "优先顺序"),
            "来源目录 / 源视频": ("来源目录 / 源视频", "优先顺序"),
            "景别": ("景别", "优先顺序"),
            "Yaw": ("Yaw", "优先顺序"),
            "Pitch": ("Pitch", "优先顺序"),
        }
        if legacy and "sort_field" not in value:
            field_name, direction = legacy_map.get(
                legacy, ("默认顺序", "优先顺序")
            )
        if direction in ("降序", "升序"):
            best_reverse = field_name in ("Face Quality", "Sharpness", "Face Pixels")
            old_reverse = direction == "降序"
            direction = (
                "优先顺序" if old_reverse == best_reverse else "反向"
            )
        if direction not in ("优先顺序", "反向"):
            direction = "优先顺序"
        return ViewSpec(
            str(value.get("name", "")),
            dict(value.get("filters", {})),
            field_name,
            direction,
            bool(value.get("best_only", False)),
            str(value.get("quick_mode", "")),
            max(1, int(value.get("limit_n", 10))),
            str(value.get("ranking_basis", "综合质量")),
        )

    def saved_views_from_data(self, folder: Path):
        return [
            self.view_spec_from_dict(item)
            for item in self.load_data(folder).get("saved_views", [])
            if isinstance(item, dict)
        ]

    def save_data(
        self,
        folder: Path,
        records,
        target: int,
        saved_views=None,
        bundle_ids=None,
        last_view=None,
        pending_composite_outputs=None,
    ):
        self.cache_root.mkdir(parents=True, exist_ok=True)
        dest = self.cache_path(folder)
        tmp = dest.with_suffix(".tmp")
        payload = {
            "version": 3,
            "analysis_version": self.analysis_version,
            "folder": str(folder.resolve()),
            "target": target,
            "saved_views": [
                asdict(value) if isinstance(value, ViewSpec) else value
                for value in (saved_views or [])
            ],
            "exported_bundle_ids": list(bundle_ids or []),
            "last_view": (
                asdict(last_view)
                if isinstance(last_view, ViewSpec)
                else last_view
            ),
            "pending_composite_outputs": list(
                pending_composite_outputs or []
            ),
            "records": [self.photo_to_dict(item) for item in records],
        }
        tmp.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        tmp.replace(dest)
