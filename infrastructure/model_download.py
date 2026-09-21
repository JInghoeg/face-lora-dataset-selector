"""Reusable SHA-verified model download helper for optional feature runtimes."""
from __future__ import annotations

import hashlib
import shutil
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ModelSpec:
    name: str
    filename: str
    url: str
    sha256: str


_DOWNLOAD_LOCK = threading.Lock()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def ensure_model(
    spec: ModelSpec,
    cache_root: Path,
    reuse_roots: Iterable[Path] = (),
) -> Path:
    folder = Path(cache_root) / spec.name
    model = folder / spec.filename

    if model.exists() and sha256_file(model) == spec.sha256:
        return model

    # Reuse an already-downloaded compatible model before contacting the network.
    for root in reuse_roots:
        root = Path(root)
        if not root.exists():
            continue
        try:
            candidates = root.rglob(spec.filename)
        except OSError:
            continue
        for candidate in candidates:
            try:
                if candidate.is_file() and sha256_file(candidate) == spec.sha256:
                    folder.mkdir(parents=True, exist_ok=True)
                    tmp_reuse = model.with_suffix(model.suffix + ".reuse")
                    shutil.copy2(candidate, tmp_reuse)
                    tmp_reuse.replace(model)
                    return model
            except OSError:
                continue

    folder.mkdir(parents=True, exist_ok=True)
    tmp = model.with_suffix(model.suffix + ".part")

    with _DOWNLOAD_LOCK:
        if model.exists() and sha256_file(model) == spec.sha256:
            return model
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass

        request = urllib.request.Request(
            spec.url,
            headers={"User-Agent": "Face-LoRA-Dataset-Selector/0.3"},
        )
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=180) as src, tmp.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    digest.update(chunk)
            actual = digest.hexdigest().lower()
            if actual != spec.sha256:
                raise RuntimeError(
                    f"{spec.name} 下载校验失败：SHA-256 {actual}，期望 {spec.sha256}"
                )
            tmp.replace(model)
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise

    return model
