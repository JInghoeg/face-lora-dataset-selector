"""Stable in-process application API consumed by the UI.

The UI should gradually route product actions through this facade instead of
calling feature/infrastructure implementations directly.
"""
from __future__ import annotations

import importlib
from pathlib import Path

from core.contracts import ExportResult
from features.ranking.service import recommend
from infrastructure.filesystem import active_image_files, copy_file

from .feature_registry import default_registry


class SelectorApplication:
    def __init__(self, registry=None):
        self.registry = registry or default_registry()
        self._composite_modules = None
        self._composite_checked = False

    def _load_composite(self, required=True):
        if not self._composite_checked:
            self._composite_checked = True
            try:
                service = importlib.import_module("features.composite.service")
                adapter = importlib.import_module("features.composite.adapter")
                self._composite_modules = (service, adapter)
            except (ImportError, ModuleNotFoundError):
                self._composite_modules = None
        if self._composite_modules is None and required:
            raise RuntimeError("Composite feature is not available.")
        return self._composite_modules

    def feature_available(self, feature_id: str) -> bool:
        if not self.registry.contains(feature_id):
            return False
        if feature_id == "composite":
            return self._load_composite(required=False) is not None
        return True

    def excluded_source_dirs(self):
        return self.registry.excluded_source_dirs()

    @property
    def composite_archive_dir(self):
        spec = next((s for s in self.registry.specs() if s.feature_id == "composite"), None)
        if spec and spec.excluded_source_dirs:
            return spec.excluded_source_dirs[0]
        return "_CompositeSplit_Originals"

    @property
    def composite_proposal_version(self):
        modules = self._load_composite(required=False)
        return int(modules[1].PROPOSAL_VERSION) if modules else 0

    def composite_proposal_from_dict(self, value):
        modules = self._load_composite(required=False)
        return modules[1].proposal_from_dict(value) if modules else None

    def composite_detect_proposal(self, image, model_cache: Path):
        modules = self._load_composite(required=True)
        return modules[1].detect_proposal(image, model_cache)

    def composite_proposal_from_detections(self, image_size, people, heads):
        modules = self._load_composite(required=True)
        return modules[1].proposal_from_detections(image_size, people, heads)

    def make_composite_detection(self, bbox, confidence, kind):
        modules = self._load_composite(required=True)
        return modules[1].Detection(bbox, confidence, kind)

    def make_composite_proposal(self, **kwargs):
        modules = self._load_composite(required=True)
        return modules[1].CompositeProposal(**kwargs)

    def active_image_files(self, folder: Path):
        return active_image_files(
            folder,
            excluded_dir_names=self.registry.excluded_source_dirs(),
        )

    def recompute_recommendations(self, records, target):
        return recommend(records, target)

    def accept_composite(self, folder: Path, source: Path, proposal, keep_mask):
        modules = self._load_composite(required=True)
        return modules[0].accept_composite(folder, source, proposal, keep_mask)

    def export_recommended(self, records, dst: Path):
        written = 0
        for record in records:
            if record.status != "推荐":
                continue
            copy_file(record.path, dst)
            written += 1
        return ExportResult(written=written)
