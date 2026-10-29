"""Qt worker for streaming background Composite -> Auto Crop enrichment."""
from __future__ import annotations

import traceback
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QObject, QThread, Signal, Slot


class BackgroundEnrichmentWorker(QObject):
    """Run model-heavy enrichment without mutating shared Photo records.

    Results are emitted back to the GUI thread one image at a time. The GUI is
    responsible for applying results to current records and persisting them.
    """

    progress = Signal(int, str, int, int, str)
    composite_ready = Signal(int, str, str, object)
    auto_crop_ready = Signal(int, str, str, object)
    item_failed = Signal(int, str, str, str, str)
    finished = Signal(int, int, int, int)
    failed = Signal(int, str)
    cancelled = Signal(int)

    def __init__(self, backend, generation: int, plan):
        super().__init__()
        self.backend = backend
        self.generation = int(generation)
        self.plan = plan

    @staticmethod
    def _load_rgb(path: Path):
        with Image.open(path) as source:
            try:
                source.seek(0)
            except EOFError:
                pass
            return ImageOps.exif_transpose(source).convert("RGB")

    def _cancelled(self) -> bool:
        thread = QThread.currentThread()
        return bool(thread and thread.isInterruptionRequested())

    def _auto_crop_one(self, job, current: int, total: int):
        if self._cancelled():
            raise InterruptedError
        proposal = self.backend.auto_crop_detect_proposal(job.path)
        if self._cancelled():
            raise InterruptedError
        self.auto_crop_ready.emit(
            self.generation,
            job.sample_id,
            str(Path(job.path).resolve()),
            proposal,
        )
        self.progress.emit(
            self.generation,
            "auto_crop",
            current,
            total,
            Path(job.path).name,
        )

    @Slot()
    def run(self):
        composite_done = 0
        auto_crop_done = 0
        errors = 0
        discovered_auto = list(self.plan.auto_crop)

        try:
            composite_total = len(self.plan.composite)
            for index, job in enumerate(self.plan.composite, 1):
                if self._cancelled():
                    raise InterruptedError
                try:
                    image = self._load_rgb(job.path)
                    proposal = self.backend.composite_detect_proposal(image)
                    if self._cancelled():
                        raise InterruptedError
                    self.composite_ready.emit(
                        self.generation,
                        job.sample_id,
                        str(Path(job.path).resolve()),
                        proposal,
                    )
                    composite_done += 1
                    self.progress.emit(
                        self.generation,
                        "composite",
                        index,
                        composite_total,
                        Path(job.path).name,
                    )

                    # Composite-clear images can immediately continue to Auto
                    # Crop; pending Composite candidates stop here.
                    if proposal is None:
                        discovered_auto.append(job)
                except InterruptedError:
                    raise
                except Exception:
                    errors += 1
                    self.item_failed.emit(
                        self.generation,
                        "composite",
                        job.sample_id,
                        str(Path(job.path).resolve()),
                        traceback.format_exc(),
                    )

            auto_total = len(discovered_auto)
            seen = set()
            deduped_auto = []
            for job in discovered_auto:
                identity = (
                    job.sample_id,
                    str(Path(job.path).resolve()).casefold(),
                )
                if identity in seen:
                    continue
                seen.add(identity)
                deduped_auto.append(job)
            auto_total = len(deduped_auto)

            for index, job in enumerate(deduped_auto, 1):
                if self._cancelled():
                    raise InterruptedError
                try:
                    self._auto_crop_one(job, index, auto_total)
                    auto_crop_done += 1
                except InterruptedError:
                    raise
                except Exception:
                    errors += 1
                    self.item_failed.emit(
                        self.generation,
                        "auto_crop",
                        job.sample_id,
                        str(Path(job.path).resolve()),
                        traceback.format_exc(),
                    )

            self.finished.emit(
                self.generation,
                composite_done,
                auto_crop_done,
                errors,
            )
        except InterruptedError:
            self.cancelled.emit(self.generation)
        except Exception:
            self.failed.emit(self.generation, traceback.format_exc())
