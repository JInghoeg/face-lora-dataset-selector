"""Duplicate grouping and human-review backend.

Owns duplicate grouping, duplicate-group queries, and the business mutations
performed by Duplicate Review. This module intentionally has no Qt dependency
and does not depend on sibling feature packages.
"""
from __future__ import annotations

from core.cancellation import check_cancelled

IGNORED_GROUP_ID = -1


def _quality_key(record):
    """Keep Duplicate Review ordering aligned with the existing quality semantics."""
    return (record.face_quality, -record.brisque, record.blur)


def group_duplicates(records, threshold=8, adjacent=16, cancelled=None):
    """Anchor-based pHash grouping; no transitive chain merging.

    This preserves the existing production semantics while moving ownership out
    of the ranking analysis feature.
    """
    for record in records:
        check_cancelled(cancelled)
        record.duplicate_group = 0

    remaining = {
        index
        for index, record in enumerate(records)
        if record.phash and not record.duplicate_ignore
    }
    group_no = 1
    while remaining:
        check_cancelled(cancelled)
        anchor = max(remaining, key=lambda i: _quality_key(records[i]))
        remaining.remove(anchor)
        members = [anchor]

        for scan_index, candidate in enumerate(list(remaining), 1):
            if scan_index % 128 == 0:
                check_cancelled(cancelled)
            left, right = records[anchor], records[candidate]
            distance = bin(left.phash ^ right.phash).count("1")
            same_source = left.source == right.source
            close = distance <= threshold or (
                same_source
                and distance <= adjacent
                and left.person_scale == right.person_scale
                and abs(left.yaw - right.yaw) <= 25
                and abs(left.pitch - right.pitch) <= 25
            )
            if close:
                members.append(candidate)
                remaining.remove(candidate)

        if len(members) > 1:
            for index in members:
                records[index].duplicate_group = group_no
            group_no += 1

    return records


def group_ids(records):
    return tuple(sorted({r.duplicate_group for r in records if r.duplicate_group}))


def group_members(records, group_id):
    if group_id == IGNORED_GROUP_ID:
        return [r for r in records if r.duplicate_ignore]
    members = [r for r in records if r.duplicate_group == group_id]
    return sorted(members, key=_quality_key, reverse=True)


def group_reviewed(records, group_id):
    members = group_members(records, group_id)
    return bool(members) and all(r.duplicate_reviewed for r in members)


def keep_best(records, group_id):
    if group_id in (None, IGNORED_GROUP_ID):
        return 0
    members = group_members(records, group_id)
    if not members:
        return 0
    best = members[0]
    for record in members:
        record.manual_status = "推荐" if record is best else "淘汰"
        record.duplicate_reviewed = True
    return len(members)


def apply_checked(records, group_id, selected_sample_ids):
    members = group_members(records, group_id)
    if not members:
        return 0
    selected = set(selected_sample_ids)
    for record in members:
        record.manual_status = "推荐" if record.sample_id in selected else "淘汰"
        record.duplicate_reviewed = True
    return len(members)


def apply_all_groups(records, selected_sample_ids):
    selected = set(selected_sample_ids)
    changed = 0
    for group_id in group_ids(records):
        changed += apply_checked(records, group_id, selected)
    return changed


def keep_all(records, group_id):
    members = group_members(records, group_id)
    for record in members:
        record.manual_status = "推荐"
        record.duplicate_reviewed = True
    return len(members)


def restore_auto(records, group_id):
    members = group_members(records, group_id)
    for record in members:
        record.manual_status = None
        record.duplicate_reviewed = False
    return len(members)


def set_ignored(records, sample_ids, ignored):
    selected = set(sample_ids)
    changed = 0
    for record in records:
        if record.sample_id not in selected:
            continue
        value = bool(ignored)
        if record.duplicate_ignore != value:
            record.duplicate_ignore = value
            changed += 1
    return changed
