"""Prepare redistributable model weights for the Windows Portable build."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Item:
    relpath: str
    url: str
    sha256: str


ITEMS = (
    Item(
        "composite_split_cache/person_detect_v1.3_s/model.onnx",
        "https://huggingface.co/deepghs/anime_person_detection/resolve/main/person_detect_v1.3_s/model.onnx?download=true",
        "6da88929438cd442e31e45ff4f934dd2d7eb9cf7a423c22885d650ee52550f90",
    ),
    Item(
        "composite_split_cache/head_detect_v2.0_s/model.onnx",
        "https://huggingface.co/deepghs/anime_head_detection/resolve/main/head_detect_v2.0_s/model.onnx?download=true",
        "6679f9b71192298bbf174d82e9e5581c3237b0c3dc67deace7cdbf686b070a00",
    ),
    Item(
        "auto_crop/skytnt_anime_seg_isnetis/isnetis.onnx",
        "https://huggingface.co/skytnt/anime-seg/resolve/main/isnetis.onnx?download=true",
        "f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99",
    ),
    Item(
        "text_cleanup/migan/migan_pipeline_v2.onnx",
        "https://huggingface.co/andraniksargsyan/migan/resolve/1538c135034b8cfe7a8472f34d09c8a5a45b17a7/migan_pipeline_v2.onnx?download=true",
        "6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def download(item: Item, root: Path) -> Path:
    target = root / item.relpath
    if target.exists() and sha256_file(target) == item.sha256:
        print(f"PASS cached {item.relpath}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    last_error = None
    for attempt in range(1, 5):
        try:
            print(f"Downloading {item.relpath} ({attempt}/4)")
            request = urllib.request.Request(
                item.url,
                headers={"User-Agent": "Face-LoRA-Dataset-Selector/v0.3.1-build"},
            )
            with urllib.request.urlopen(request, timeout=300) as src, tmp.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            actual = sha256_file(tmp)
            if actual != item.sha256:
                raise RuntimeError(
                    f"SHA256 mismatch for {item.relpath}: {actual} != {item.sha256}"
                )
            tmp.replace(target)
            return target
        except Exception as exc:
            last_error = exc
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
            if attempt < 4:
                time.sleep(attempt * 3)
    raise RuntimeError(f"Failed to download {item.relpath}: {last_error}")


def verify(root: Path) -> None:
    failures = []
    for item in ITEMS:
        path = root / item.relpath
        if not path.exists():
            failures.append(f"missing: {item.relpath}")
            continue
        actual = sha256_file(path)
        if actual != item.sha256:
            failures.append(f"hash: {item.relpath}: {actual}")
        else:
            print(f"PASS {item.relpath}")
    if failures:
        raise SystemExit("\n".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="models")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    if not args.verify_only:
        for item in ITEMS:
            download(item, root)
    verify(root)


if __name__ == "__main__":
    main()
