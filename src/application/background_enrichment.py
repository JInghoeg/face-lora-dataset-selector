"""Application-level orchestration policy for background enrichment.

This module coordinates sequencing between optional sibling features without
importing their internals. It only decides which current records are eligible
for Composite scanning or Auto Crop pre-scan.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnrichmentJob:
    sample_id: str
    path: Path


@dataclass(frozen=True)
class BackgroundEnrichmentPlan:
    composite: tuple[EnrichmentJob, ...] = ()
    auto_crop: tuple[EnrichmentJob, ...] = ()

    @property
    def total(self) -> int:
        return len(self.composite) + len(self.auto_crop)


def _job(record) -> EnrichmentJob:
    return EnrichmentJob(
        sample_id=str(getattr(record, "sample_id", "") or ""),
        path=Path(record.path),
    )


def composite_allows_auto_crop(record, proposal_version: int) -> bool:
    """Return whether Auto Crop may run without violating Composite ordering."""
    if int(getattr(record, "composite_scan_version", 0)) != int(proposal_version):
        return False
    proposal = getattr(record, "composite_proposal", None)
    if proposal is None:
        return True
    return getattr(proposal, "decision", None) == "rejected"


def build_background_enrichment_plan(
    records,
    *,
    composite_proposal_version: int,
    auto_crop_state_current,
    composite_available: bool = True,
    auto_crop_available: bool = True,
) -> BackgroundEnrichmentPlan:
    """Build a read-only plan for current 推荐 records.

    Rules:
    - stale Composite state is scanned first when Composite is available;
    - pending/accepted Composite candidates never enter Auto Crop;
    - Composite-clear or explicitly rejected records may enter Auto Crop;
    - Auto Crop only receives records whose current scan state is missing/stale.
    """
    composite_jobs = []
    auto_crop_jobs = []

    for record in records:
        if getattr(record, "status", None) != "推荐":
            continue

        if composite_available:
            if int(getattr(record, "composite_scan_version", 0)) != int(
                composite_proposal_version
            ):
                composite_jobs.append(_job(record))
                continue
            if not composite_allows_auto_crop(record, composite_proposal_version):
                continue

        if auto_crop_available and not auto_crop_state_current(record):
            auto_crop_jobs.append(_job(record))

    return BackgroundEnrichmentPlan(
        composite=tuple(composite_jobs),
        auto_crop=tuple(auto_crop_jobs),
    )
