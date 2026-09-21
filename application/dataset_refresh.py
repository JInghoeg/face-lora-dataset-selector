"""Application service for incremental dataset refresh.

Owns cache/file-diff orchestration. It is UI-agnostic and reports status/progress
through callbacks supplied by the presentation adapter.
"""
from __future__ import annotations

from core.contracts import DatasetRefreshResult
from core.models import derive_eligibility
from features.ranking.analysis import (
    AnalysisEngine,
    base_status,
    group_duplicates,
    new_sample_id,
)
from infrastructure.filesystem import sha256_file


class DatasetRefreshService:
    def __init__(self, cache, active_files):
        self.cache = cache
        self.active_files = active_files

    def refresh(self, folder, status=None, progress=None):
        status = status or (lambda _message: None)
        progress = progress or (lambda _current, _total, _name: None)

        files = self.active_files(folder)
        if not files:
            raise RuntimeError("没有找到图片。")

        old = self.cache.load_cached(folder)
        old_by_hash = self.cache.load_cached_by_hash(folder)
        history = self.cache.historical_records(folder)
        legacy_manual = self.cache.legacy_manual_states(folder)
        had_v3_cache = bool(old)

        result = [None] * len(files)
        pending = []
        used_sample_ids = set()
        current_keys = {self.cache.key(path) for path in files}
        deleted_count = sum(1 for key in old if key not in current_keys)
        added_count = 0
        modified_count = 0
        unchanged_count = 0

        for index, path in enumerate(files):
            stat = path.stat()
            cached = old.get(self.cache.key(path))
            if (
                cached
                and cached.get("file_size") == stat.st_size
                and cached.get("mtime_ns") == stat.st_mtime_ns
            ):
                restored = self.cache.photo_from_dict(
                    cached, path, stat.st_size, stat.st_mtime_ns
                )
                if (
                    not restored.sample_id
                    or restored.sample_id in used_sample_ids
                ):
                    restored.sample_id = new_sample_id()
                used_sample_ids.add(restored.sample_id)
                result[index] = restored
                unchanged_count += 1
            else:
                pending.append(
                    (index, path, stat.st_size, stat.st_mtime_ns, cached)
                )
                if cached:
                    modified_count += 1
                else:
                    added_count += 1

        todo = []
        for index, path, size, mtime, path_cache in pending:
            content_sha = sha256_file(path)
            same = None
            if (
                path_cache
                and path_cache.get("content_sha256") == content_sha
                and path_cache.get("sample_id") not in used_sample_ids
            ):
                same = path_cache
            else:
                candidates = [
                    item
                    for item in old_by_hash.get(content_sha, [])
                    if item.get("sample_id")
                    and item.get("sample_id") not in used_sample_ids
                ]
                if len(candidates) == 1:
                    same = candidates[0]

            if same:
                restored = self.cache.photo_from_dict(
                    same, path, size, mtime
                )
                restored.content_sha256 = content_sha
                if (
                    not restored.sample_id
                    or restored.sample_id in used_sample_ids
                ):
                    restored.sample_id = new_sample_id()
                used_sample_ids.add(restored.sample_id)
                result[index] = restored
                if path_cache:
                    modified_count = max(0, modified_count - 1)
                unchanged_count += 1
            else:
                todo.append((index, path, size, mtime, content_sha))

        changed_count = len(todo)
        if todo:
            status(f"分析 {len(todo)} 张变化图片；其余恢复缓存…")
            with AnalysisEngine() as engine:
                for number, (index, path, size, mtime, content_sha) in enumerate(
                    todo, 1
                ):
                    result[index] = engine.analyze_one(
                        path, size, mtime, content_sha
                    )
                    progress(number, len(todo), path.name)

        records = [item for item in result if item]
        for record in records:
            historical = history.get(self.cache.key(record.path))
            same_content = bool(
                historical
                and historical.get("content_sha256")
                and historical.get("content_sha256") == record.content_sha256
            )
            if same_content:
                if historical.get("sample_id"):
                    record.sample_id = historical["sample_id"]
                record.manual_status = historical.get("manual_status")
                record.duplicate_ignore = bool(
                    historical.get("duplicate_ignore", False)
                )
                record.duplicate_reviewed = bool(
                    historical.get("duplicate_reviewed", False)
                )
                record.ai_suggestion = self.cache.ai_suggestion_from_dict(
                    historical.get("ai_suggestion")
                )
            elif not record.manual_status:
                record.manual_status = legacy_manual.get(
                    self.cache.key(record.path)
                )
            derive_eligibility(record)

        group_duplicates(records)
        base_status(records)

        return DatasetRefreshResult(
            records=records,
            had_v3_cache=had_v3_cache,
            changed_count=changed_count,
            added_count=added_count,
            modified_count=modified_count,
            deleted_count=deleted_count,
            unchanged_count=unchanged_count,
        )

    @staticmethod
    def analyze_generated(items, progress=None):
        progress = progress or (lambda _current, _total, _name: None)
        output = []
        if not items:
            return output
        with AnalysisEngine() as engine:
            total = len(items)
            for index, (path, status_value) in enumerate(items, 1):
                stat = path.stat()
                record = engine.analyze_one(
                    path, stat.st_size, stat.st_mtime_ns
                )
                record.manual_status = status_value
                derive_eligibility(record)
                output.append(record)
                progress(index, total, path.name)
        return output
