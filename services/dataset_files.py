"""Dataset file-lifecycle service.

Owns active-image enumeration and materialization/archive file operations.
No Qt/UI state is referenced here.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif'
}
COMPOSITE_ARCHIVE_DIR = '_CompositeSplit_Originals'


def is_composite_archive_path(path: Path, folder: Path) -> bool:
    try:
        rel = path.resolve().relative_to(folder.resolve())
    except Exception:
        return False
    archive = COMPOSITE_ARCHIVE_DIR.casefold()
    return any(part.casefold() == archive for part in rel.parts[:-1])


def active_image_files(folder: Path):
    return sorted(
        (
            path
            for path in folder.rglob('*')
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not is_composite_archive_path(path, folder)
        ),
        key=lambda path: str(path).lower(),
    )


def unique_output_path(dst: Path, name: str):
    out = dst / name
    if not out.exists():
        return out
    stem = out.stem
    suffix = out.suffix
    index = 1
    while True:
        candidate = dst / f'{stem}_{index}{suffix}'
        if not candidate.exists():
            return candidate
        index += 1


def composite_output_suffix(source: Path):
    suffix = source.suffix.lower()
    return suffix if suffix in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff') else '.png'


def save_training_crop(source: Path, box, out: Path):
    with Image.open(source) as image:
        try:
            image.seek(0)
        except EOFError:
            pass
        image = ImageOps.exif_transpose(image).convert('RGB')
        width, height = image.size
        x0, y0, x1, y1 = map(int, box)
        x0 = max(0, min(width, x0))
        x1 = max(0, min(width, x1))
        y0 = max(0, min(height, y0))
        y1 = max(0, min(height, y1))
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f'无效 Composite Split 裁剪框：{box}')
        crop = image.crop((x0, y0, x1, y1))
        suffix = out.suffix.lower()
        if suffix in ('.jpg', '.jpeg'):
            crop.save(out, quality=95, subsampling=0)
        elif suffix == '.webp':
            crop.save(out, quality=95, method=6)
        else:
            crop.save(out)
        return crop.size


def composite_output_statuses(outputs, keep_mask):
    if len(outputs) != len(keep_mask):
        raise ValueError('Composite 输出选择数量与生成结果不一致')
    return [
        (path, '推荐' if keep else '淘汰')
        for path, keep in zip(outputs, keep_mask)
    ]


def materialize_composite_source(folder: Path, source: Path, proposal):
    outputs = []
    suffix = composite_output_suffix(source)
    tag = 'group' if proposal.mode == 'group_crop' else 'split'
    try:
        for index, box in enumerate(proposal.output_boxes, 1):
            out = unique_output_path(
                source.parent,
                f'{source.stem}__{tag}_{index:02d}{suffix}',
            )
            save_training_crop(source, box, out)
            outputs.append(out)

        try:
            relative = source.resolve().relative_to(folder.resolve())
        except Exception:
            relative = Path(source.name)

        archive = folder / COMPOSITE_ARCHIVE_DIR / relative
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive = unique_output_path(archive.parent, archive.name)
        shutil.move(str(source), str(archive))
        return outputs, archive
    except Exception:
        for out in outputs:
            try:
                if out.exists():
                    out.unlink()
            except OSError:
                pass
        raise
