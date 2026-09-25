"""Composite Split product service.

Owns Composite-specific workflow semantics while delegating generic file I/O to
infrastructure adapters. No Qt/widget imports are allowed here.
"""
from __future__ import annotations

from pathlib import Path

from core.contracts import CompositeMaterializationResult, MaterializedOutput
from infrastructure.filesystem import (
    archive_source,
    image_output_suffix,
    save_crop,
    unique_output_path,
)

COMPOSITE_ARCHIVE_DIR = '_CompositeSplit_Originals'


def accept_composite(folder: Path, source: Path, proposal, keep_mask):
    if len(proposal.output_boxes) != len(keep_mask):
        raise ValueError('Composite 输出选择数量与建议输出不一致')

    outputs = []
    suffix = image_output_suffix(source)
    tag = 'group' if proposal.mode == 'group_crop' else 'split'

    try:
        for index, (box, keep) in enumerate(zip(proposal.output_boxes, keep_mask), 1):
            out = unique_output_path(
                source.parent,
                f'{source.stem}__{tag}_{index:02d}{suffix}',
            )
            save_crop(source, box, out)
            outputs.append(
                MaterializedOutput(
                    path=out,
                    status='推荐' if keep else '淘汰',
                )
            )

        archived = archive_source(folder, source, COMPOSITE_ARCHIVE_DIR)
        return CompositeMaterializationResult(
            archived_source=archived,
            outputs=tuple(outputs),
        )
    except Exception:
        for output in outputs:
            try:
                if output.path.exists():
                    output.path.unlink()
            except OSError:
                pass
        raise
