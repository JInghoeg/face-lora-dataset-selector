"""Filesystem adapter used by application/features.

This module owns generic image/file operations only. It intentionally does not
know Composite/AutoCrop/Duplicate business semantics.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif'
}


def is_excluded_path(path: Path, folder: Path, excluded_dir_names: Iterable[str]) -> bool:
    try:
        rel = path.resolve().relative_to(folder.resolve())
    except Exception:
        return False
    excluded = {name.casefold() for name in excluded_dir_names}
    return any(part.casefold() in excluded for part in rel.parts[:-1])


def active_image_files(folder: Path, excluded_dir_names=()):
    return sorted(
        (
            path
            for path in folder.rglob('*')
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and not is_excluded_path(path, folder, excluded_dir_names)
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


def image_output_suffix(source: Path):
    suffix = source.suffix.lower()
    return suffix if suffix in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff') else '.png'


def save_crop(source: Path, box, out: Path):
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
            raise ValueError(f'无效裁剪框：{box}')
        crop = image.crop((x0, y0, x1, y1))
        suffix = out.suffix.lower()
        if suffix in ('.jpg', '.jpeg'):
            crop.save(out, quality=95, subsampling=0)
        elif suffix == '.webp':
            crop.save(out, quality=95, method=6)
        else:
            crop.save(out)
        return crop.size


def archive_source(folder: Path, source: Path, archive_dir_name: str):
    try:
        relative = source.resolve().relative_to(folder.resolve())
    except Exception:
        relative = Path(source.name)
    archive = folder / archive_dir_name / relative
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive = unique_output_path(archive.parent, archive.name)
    shutil.move(str(source), str(archive))
    return archive


def copy_file(source: Path, dst_dir: Path):
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = unique_output_path(dst_dir, source.name)
    shutil.copy2(source, out)
    return out
