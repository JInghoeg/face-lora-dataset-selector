"""Stable in-process application API consumed by the UI.

Optional built-in features use guarded static imports: the app can start when an
optional feature is absent, while PyInstaller can still discover bundled default
features without a dynamic-plugin system.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.contracts import ExportResult
from features.ranking.service import recommend
from features.ranking.analysis import group_duplicates
from infrastructure.filesystem import active_image_files, copy_file
from infrastructure.cache_store import DatasetCache
from .dataset_refresh import DatasetRefreshService

from .feature_registry import default_registry

try:
    from features.composite import adapter as _composite_adapter
    from features.composite import service as _composite_service
except ImportError:
    _composite_adapter = None
    _composite_service = None


class SelectorApplication:
    def __init__(self, registry=None):
        self.registry = registry or default_registry()
        project_root = Path(__file__).resolve().parents[1]
        user_data_root = Path(
            os.environ.get("LOCALAPPDATA")
            or (Path.home() / "AppData" / "Local")
        ) / "Face LoRA Dataset Selector"
        self.cache = DatasetCache(
            cache_root=user_data_root / "cache",
            legacy_cache_root=project_root / "cache",
            analysis_version=4,
            proposal_loader=self.composite_proposal_from_dict,
            proposal_version_getter=lambda: self.composite_proposal_version,
        )
        self.cache.migrate_legacy()
        self.refresh_service = DatasetRefreshService(
            self.cache, self.active_image_files
        )

    def _composite_modules(self, required=True):
        modules = (
            (_composite_service, _composite_adapter)
            if _composite_service is not None and _composite_adapter is not None
            else None
        )
        if modules is None and required:
            raise RuntimeError("Composite feature is not available.")
        return modules

    def feature_available(self, feature_id: str) -> bool:
        if not self.registry.contains(feature_id):
            return False
        if feature_id == "composite":
            return self._composite_modules(required=False) is not None
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
        modules = self._composite_modules(required=False)
        return int(modules[1].PROPOSAL_VERSION) if modules else 0

    def composite_proposal_from_dict(self, value):
        modules = self._composite_modules(required=False)
        return modules[1].proposal_from_dict(value) if modules else None

    def composite_detect_proposal(self, image, model_cache: Path):
        return self._composite_modules(required=True)[1].detect_proposal(image, model_cache)

    def composite_proposal_from_detections(self, image_size, people, heads):
        return self._composite_modules(required=True)[1].proposal_from_detections(
            image_size, people, heads
        )

    def make_composite_detection(self, bbox, confidence, kind):
        return self._composite_modules(required=True)[1].Detection(
            bbox, confidence, kind
        )

    def make_composite_proposal(self, **kwargs):
        return self._composite_modules(required=True)[1].CompositeProposal(**kwargs)

    def active_image_files(self, folder: Path):
        return active_image_files(
            folder,
            excluded_dir_names=self.registry.excluded_source_dirs(),
        )

    @property
    def cache_root(self):
        return self.cache.cache_root

    def load_dataset_state(self, folder: Path):
        return self.cache.load_data(folder)

    def saved_views(self, folder: Path):
        return self.cache.saved_views_from_data(folder)

    def decode_view_spec(self, value):
        return self.cache.view_spec_from_dict(value)

    def save_dataset_state(
        self,
        folder: Path,
        records,
        target,
        saved_views=None,
        bundle_ids=None,
        last_view=None,
        pending_composite_outputs=None,
    ):
        return self.cache.save_data(
            folder,
            records,
            target,
            saved_views,
            bundle_ids,
            last_view,
            pending_composite_outputs,
        )

    def refresh_dataset(self, folder: Path, status=None, progress=None):
        return self.refresh_service.refresh(
            folder, status=status, progress=progress
        )

    def analyze_generated(self, items, progress=None):
        records = self.refresh_service.analyze_generated(
            items, progress=progress
        )
        for record in records:
            record.composite_scan_version = self.composite_proposal_version
            record.composite_proposal = None
        return records

    def recompute_recommendations(self, records, target):
        return recommend(records, target)

    def regroup_duplicates(self, records, threshold=8, adjacent=16):
        group_duplicates(records, threshold=threshold, adjacent=adjacent)
        return records

    def accept_composite(self, folder: Path, source: Path, proposal, keep_mask):
        return self._composite_modules(required=True)[0].accept_composite(
            folder, source, proposal, keep_mask
        )

    def export_recommended(self, records, dst: Path):
        written = 0
        for record in records:
            if record.status != "推荐":
                continue
            copy_file(record.path, dst)
            written += 1
        return ExportResult(written=written)
