"""Stable cross-layer DTOs and feature metadata.

No Qt, filesystem implementation, model runtime, or feature implementation imports
belong in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    display_name: str
    optional: bool = True
    excluded_source_dirs: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MaterializedOutput:
    path: Path
    status: str


@dataclass(frozen=True)
class CompositeMaterializationResult:
    archived_source: Path
    outputs: Tuple[MaterializedOutput, ...]


@dataclass(frozen=True)
class RecommendationSummary:
    target: int
    automatic_recommended: int
    manual_recommended: int
    effective_recommended: int


@dataclass(frozen=True)
class ExportResult:
    written: int


@dataclass
class DatasetRefreshResult:
    records: list
    had_v3_cache: bool = False
    changed_count: int = 0
    added_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    unchanged_count: int = 0
