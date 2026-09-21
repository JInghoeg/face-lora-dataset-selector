"""Recommendation service for the selector core.

This module owns automatic recommendation/ranking semantics and intentionally
has no Qt, filesystem, cache, or model-runtime dependencies.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from core.contracts import RecommendationSummary

SCALES = ('近景/头肩', '半身', '大半身', '全身')
YAWS = ('正脸', '左3/4', '右3/4', '左侧脸', '右侧脸')

AUTO_RECOMMEND_BLOCKING_FLAGS = {
    'no_face_full_body_review',
    'secondary_faces_detected',
    'probable_multi_person',
    'low_face_pixels',
    'extreme_exposure',
    'face_detection_error',
    'face_quality_error',
    'head_pose_error',
    'face_sharpness_error',
    'brisque_error',
    'pose_analysis_error',
}


def finding_text(finding):
    return finding.detail or finding.code


def rank(record):
    """Transparent lexicographic quality ranking: FIQA, BRISQUE, sharpness."""
    return (record.face_quality, -record.brisque, record.blur)


def recommendation_blockers(record):
    out = []
    if record.hard_rejects:
        out.extend('硬淘汰：' + finding_text(x) for x in record.hard_rejects)
    out.extend(
        '需先复核：' + finding_text(x)
        for x in record.review_flags
        if x.code in AUTO_RECOMMEND_BLOCKING_FLAGS
    )
    for finding in record.review_flags:
        if finding.code == 'low_face_quality' and record.angle_class not in ('左侧脸', '右侧脸'):
            out.append('需先复核：' + finding_text(finding))
    if record.brisque > 70:
        out.append(f'BRISQUE {record.brisque:.1f} > 70')
    if record.blur < 40:
        out.append(f'主脸清晰度 {record.blur:.1f} < 40')
    return out


def recommendation_qualified(record):
    """Side-profile FIQA stays non-blocking while severe frontal issues can block."""
    return not recommendation_blockers(record)


def group_entries(records, group, qualified=False):
    entries = [r for r in records if r.duplicate_group == group]
    if qualified:
        good = [r for r in entries if recommendation_qualified(r)]
        entries = good or entries
    return sorted(entries, key=rank, reverse=True)


def group_best(records):
    """Return only the best representative for each duplicate group."""
    result = []
    seen = set()
    for record in sorted(records, key=rank, reverse=True):
        if record.duplicate_group and record.duplicate_group in seen:
            continue
        result.append(record)
        if record.duplicate_group:
            seen.add(record.duplicate_group)
    return result


def _allocate(total, names, weights):
    if not names:
        return {x: 0 for x in names}
    weight_sum = sum(weights[x] for x in names)
    raw = {x: total * weights[x] / weight_sum for x in names}
    out = {x: int(raw[x]) for x in names}
    for name in sorted(names, key=lambda x: raw[x] - out[x], reverse=True)[: total - sum(out.values())]:
        out[name] += 1
    return out


def recommend(records, target):
    """Compute the automatic baseline independently from all manual overrides."""
    for record in records:
        record.recommendation_reasons = []
        record.auto_status = '淘汰' if record.eligibility == 'REJECT' else '备选'

    eligible = [r for r in records if recommendation_qualified(r)]
    eligible_ids = {id(r) for r in eligible}
    for record in records:
        if id(record) not in eligible_ids:
            record.recommendation_reasons = recommendation_blockers(record) or ['未通过自动推荐基础门槛']

    pool = group_best(eligible)
    pool_ids = {id(r) for r in pool}
    buckets = defaultdict(list)
    scale_buckets = defaultdict(list)

    for record in eligible:
        if id(record) not in pool_ids:
            group_rank, group_size = (1, 1)
            if record.duplicate_group:
                entries = group_entries(eligible, record.duplicate_group)
                group_rank = entries.index(record) + 1 if record in entries else 0
                group_size = len(entries)
            record.recommendation_reasons = (
                [f'Duplicate Group {record.duplicate_group} 已保留更优代表（组内 {group_rank}/{group_size}）']
                if record.duplicate_group
                else ['同类候选中已有更优代表']
            )

    for record in pool:
        buckets[record.person_scale, record.angle_class].append(record)
        scale_buckets[record.person_scale].append(record)

    for values in list(buckets.values()) + list(scale_buckets.values()):
        values.sort(key=rank, reverse=True)

    remaining = max(0, target)
    scale_quota = _allocate(
        remaining,
        [x for x in SCALES if scale_buckets[x]],
        {'近景/头肩': .35, '半身': .30, '大半身': .20, '全身': .15},
    )
    used_groups = set()
    chosen = []
    chosen_ids = set()
    got = Counter()

    def take(candidates, count):
        for record in candidates:
            if len(chosen) >= remaining or count <= 0:
                return
            if id(record) in chosen_ids or (
                record.duplicate_group and record.duplicate_group in used_groups
            ):
                continue
            chosen.append(record)
            chosen_ids.add(id(record))
            got[record.person_scale] += 1
            count -= 1
            if record.duplicate_group:
                used_groups.add(record.duplicate_group)

    for scale in [x for x in SCALES if scale_buckets[x]]:
        yaw_names = [x for x in YAWS if buckets[scale, x]]
        for yaw, count in _allocate(
            scale_quota[scale],
            yaw_names,
            {'正脸': .35, '左3/4': .20, '右3/4': .20, '左侧脸': .125, '右侧脸': .125},
        ).items():
            take(buckets[scale, yaw], count)
        take(scale_buckets[scale], max(0, scale_quota[scale] - got[scale]))

    while len(chosen) < remaining:
        progress = False
        for scale in sorted(scale_quota, key=lambda x: got[x] / max(1, scale_quota[x])):
            before = len(chosen)
            take(scale_buckets[scale], 1)
            progress |= len(chosen) > before
        if not progress:
            break

    chosen_ids = {id(r) for r in chosen}
    for record in chosen:
        record.auto_status = '推荐'
        record.recommendation_reasons = [
            f'自动推荐：通过基础门槛，并用于补足 {record.person_scale} / {record.angle_class} 覆盖'
        ]

    for record in pool:
        if id(record) not in chosen_ids and not record.recommendation_reasons:
            record.recommendation_reasons = [
                f'已通过基础门槛，但当前自动目标 {target} 张的景别×角度覆盖分配未选中'
                f'（{record.person_scale} / {record.angle_class}）'
            ]

    for record in records:
        if record.manual_status:
            record.recommendation_reasons.insert(
                0,
                f'人工状态优先：{record.manual_status}（自动基线：{record.auto_status}）',
            )

    return RecommendationSummary(
        target=int(target),
        automatic_recommended=sum(r.auto_status == '推荐' for r in records),
        manual_recommended=sum(r.manual_status == '推荐' for r in records),
        effective_recommended=sum(r.status == '推荐' for r in records),
    )
