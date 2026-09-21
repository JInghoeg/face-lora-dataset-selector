"""Stable in-process application API consumed by the UI.

The UI should gradually route product actions through this facade instead of
calling feature/infrastructure implementations directly.
"""
from __future__ import annotations

from pathlib import Path

from core.contracts import ExportResult
from features.composite.service import accept_composite
from features.ranking.service import recommend
from infrastructure.filesystem import active_image_files, copy_file

from .feature_registry import default_registry


class SelectorApplication:
    def __init__(self, registry=None):
        self.registry = registry or default_registry()

    def active_image_files(self, folder: Path):
        return active_image_files(
            folder,
            excluded_dir_names=self.registry.excluded_source_dirs(),
        )

    def recompute_recommendations(self, records, target):
        return recommend(records, target)

    def accept_composite(self, folder: Path, source: Path, proposal, keep_mask):
        if not self.registry.contains('composite'):
            raise RuntimeError('Composite feature is not available.')
        return accept_composite(folder, source, proposal, keep_mask)

    def export_recommended(self, records, dst: Path):
        written = 0
        for record in records:
            if record.status != '推荐':
                continue
            copy_file(record.path, dst)
            written += 1
        return ExportResult(written=written)
