"""Background Composite -> Auto Crop orchestration smoke."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from application.background_enrichment import build_background_enrichment_plan
from ui.qt.background_enrichment import BackgroundEnrichmentWorker


def record(path, *, status="推荐", version=0, proposal=None, current=False):
    item = SimpleNamespace(
        path=Path(path),
        sample_id=Path(path).stem,
        status=status,
        composite_scan_version=version,
        composite_proposal=proposal,
        feature_state={},
    )
    item._auto_current = bool(current)
    return item


def plan_smoke(root: Path):
    stale = record(root / "stale.png", version=0)
    clear = record(root / "clear.png", version=7)
    pending = record(
        root / "pending.png",
        version=7,
        proposal=SimpleNamespace(decision="pending"),
    )
    rejected = record(
        root / "rejected.png",
        version=7,
        proposal=SimpleNamespace(decision="rejected"),
    )
    cached = record(root / "cached.png", version=7, current=True)
    backup = record(root / "backup.png", status="备选", version=0)

    plan = build_background_enrichment_plan(
        [stale, clear, pending, rejected, cached, backup],
        composite_proposal_version=7,
        auto_crop_state_current=lambda item: item._auto_current,
        composite_available=True,
        auto_crop_available=True,
    )

    assert [job.sample_id for job in plan.composite] == ["stale"]
    assert [job.sample_id for job in plan.auto_crop] == ["clear", "rejected"]
    assert plan.total == 3
    return plan, stale, clear, rejected


class FakeBackend:
    def __init__(self):
        self.composite_calls = []
        self.auto_calls = []

    def feature_available(self, feature_id):
        return feature_id in {"composite", "auto_crop"}

    def composite_detect_proposal(self, image):
        self.composite_calls.append(image.size)
        return None

    def auto_crop_detect_proposal(self, path):
        self.auto_calls.append(Path(path).name)
        return {"candidate": Path(path).name}


def worker_streaming_smoke(plan, records):
    backend = FakeBackend()
    worker = BackgroundEnrichmentWorker(backend, 11, plan)
    composite = []
    auto = []
    progress = []
    finished = []
    failures = []

    worker.composite_ready.connect(
        lambda generation, sample_id, path, proposal:
            composite.append((generation, sample_id, Path(path).name, proposal))
    )
    worker.auto_crop_ready.connect(
        lambda generation, sample_id, path, proposal:
            auto.append((generation, sample_id, Path(path).name, proposal))
    )
    worker.progress.connect(
        lambda generation, kind, current, total, name:
            progress.append((generation, kind, current, total, name))
    )
    worker.finished.connect(
        lambda generation, composite_done, auto_done, errors:
            finished.append((generation, composite_done, auto_done, errors))
    )
    worker.failed.connect(lambda generation, error: failures.append((generation, error)))

    before = [dict(item.feature_state) for item in records]
    worker.run()
    after = [dict(item.feature_state) for item in records]

    assert failures == [], failures
    assert finished == [(11, 1, 3, 0)], finished
    assert [item[1] for item in composite] == ["stale"], composite
    assert [item[1] for item in auto] == ["clear", "rejected", "stale"], auto
    assert before == after, "worker must not mutate shared Photo state"
    assert backend.auto_calls == ["clear.png", "rejected.png", "stale.png"]
    assert any(row[1] == "composite" for row in progress)
    assert any(row[1] == "auto_crop" for row in progress)


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name in (
            "stale.png",
            "clear.png",
            "pending.png",
            "rejected.png",
            "cached.png",
            "backup.png",
        ):
            Image.new("RGB", (32, 24), (12, 34, 56)).save(root / name)

        plan, stale, clear, rejected = plan_smoke(root)
        worker_streaming_smoke(plan, [stale, clear, rejected])

    print("Background enrichment smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
