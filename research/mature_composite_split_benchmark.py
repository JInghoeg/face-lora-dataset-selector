"""Composite Split research using the existing DeepGHS person detector.

Purpose:
- find images containing multiple detected people/character views;
- export each detected person as a separate crop;
- keep the detector itself completely upstream.

This is a research benchmark only. It does not modify source images and does not
yet decide which detections should become production outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    from imgutils.detect import detect_person
except ImportError as exc:
    raise SystemExit(
        "dghs-imgutils is not installed. Run research\\运行成熟人物检测基线.bat first."
    ) from exc

from mature_person_benchmark import (
    CONF_THRESHOLD,
    IOU_THRESHOLD,
    MODEL_NAME,
    box_area,
    fit,
)

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"
}


def local_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))


def default_dataset() -> Path:
    candidate = Path(__file__).resolve().parents[2] / "渥尔比"
    if candidate.exists():
        return candidate
    raise RuntimeError("未找到默认渥尔比数据集，请用 --folder 指定。")


def image_files(folder: Path):
    for p in sorted(folder.rglob("*"), key=lambda x: str(x).casefold()):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            yield p


def reading_order(detections):
    """Order already-detected people for deterministic split filenames.

    This does not change detection boxes. It only orders outputs:
    horizontal layouts left->right; vertical layouts top->bottom.
    """
    if len(detections) <= 1:
        return detections

    centers = []
    for det in detections:
        x0, y0, x1, y1 = det[0]
        centers.append(((x0 + x1) / 2, (y0 + y1) / 2, det))

    xs = [x for x, _, _ in centers]
    ys = [y for _, y, _ in centers]
    if (max(xs) - min(xs)) >= (max(ys) - min(ys)):
        centers.sort(key=lambda t: (t[0], t[1]))
    else:
        centers.sort(key=lambda t: (t[1], t[0]))
    return [det for _, _, det in centers]


def overlay(image: Image.Image, detections) -> Image.Image:
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    width = max(3, round(min(out.size) * 0.005))
    for idx, (box, kind, score) in enumerate(reading_order(detections), 1):
        x0, y0, x1, y1 = box
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline="red", width=width)
        draw.text(
            (x0 + 4, max(0, y0 - 18)),
            f"{idx} {kind} {score:.3f}",
            fill="red",
        )
    return out


def export_splits(image: Image.Image, detections, out_dir: Path, stem: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for idx, (box, kind, score) in enumerate(reading_order(detections), 1):
        crop = image.crop(tuple(box)).convert("RGB")
        path = out_dir / f"{stem}_split_{idx:02d}.jpg"
        crop.save(path, quality=95)
        outputs.append(
            {
                "index": idx,
                "box": list(box),
                "type": kind,
                "score": float(score),
                "area": box_area(box),
                "output": str(path),
            }
        )
    return outputs


def make_contact_sheet(rows: list[dict], out: Path):
    tile_w, tile_h = 420, 340
    cols = 3
    rows_per_page = 4

    for page_no, start in enumerate(range(0, len(rows), rows_per_page), 1):
        batch = rows[start:start + rows_per_page]
        page = Image.new("RGB", (cols * tile_w, len(batch) * tile_h), "white")
        draw = ImageDraw.Draw(page)

        for row_idx, item in enumerate(batch):
            with Image.open(item["path"]) as im:
                im.seek(0)
                original = ImageOps.exif_transpose(im).convert("RGB")

            detections = [
                (tuple(d["box"]), d["type"], d["score"])
                for d in item["detections"]
            ]
            ordered = reading_order(detections)

            montage = Image.new("RGB", original.size, "white")
            if ordered:
                crops = [original.crop(tuple(d[0])).convert("RGB") for d in ordered]
                widths = [c.width for c in crops]
                heights = [c.height for c in crops]
                total_w = max(1, sum(widths))
                max_h = max(heights)
                montage = Image.new("RGB", (total_w, max_h), "white")
                x = 0
                for crop in crops:
                    montage.paste(crop, (x, (max_h - crop.height) // 2))
                    x += crop.width

            visuals = [
                ("ORIGINAL", original),
                ("RAW DEEPGHS DETECTIONS", overlay(original, detections)),
                ("RAW SPLIT OUTPUTS", montage),
            ]

            for col, (title, image) in enumerate(visuals):
                x = col * tile_w
                y = row_idx * tile_h
                page.paste(fit(image, (tile_w - 16, tile_h - 58)), (x + 8, y + 28))
                draw.text((x + 8, y + 7), title, fill="black")

            draw.text(
                (8, row_idx * tile_h + tile_h - 24),
                f"{Path(item['path']).name[:90]} | detections={len(detections)}",
                fill="black",
            )

        page.save(out / f"contact_{page_no:02d}.jpg", quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--target", type=int, default=12)
    parser.add_argument("--scan-limit", type=int, default=100)
    args = parser.parse_args()

    folder = args.folder or default_dataset()
    if not folder.exists():
        raise RuntimeError(f"数据集不存在: {folder}")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = (
        local_root()
        / "Face LoRA Dataset Selector"
        / "research"
        / "mature_composite_split"
        / stamp
    )
    split_root = out / "split_outputs"
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    scanned = 0

    print(f"Dataset: {folder}", flush=True)
    print(f"Upstream detector: {MODEL_NAME}", flush=True)
    print(
        f"Stop after {args.target} multi-person images or {args.scan_limit} scanned images.",
        flush=True,
    )

    for path in image_files(folder):
        if scanned >= args.scan_limit or len(rows) >= args.target:
            break
        scanned += 1
        print(f"[scan {scanned}] {path.name}", flush=True)

        with Image.open(path) as im:
            try:
                im.seek(0)
            except EOFError:
                pass
            image = ImageOps.exif_transpose(im).convert("RGB")

        detections = detect_person(
            image,
            model_name=MODEL_NAME,
            conf_threshold=CONF_THRESHOLD,
            iou_threshold=IOU_THRESHOLD,
        )
        if len(detections) < 2:
            continue

        sample_dir = split_root / f"{len(rows) + 1:02d}_{path.stem[:70]}"
        outputs = export_splits(image, detections, sample_dir, path.stem[:70])
        rows.append(
            {
                "path": str(path),
                "detections": [
                    {
                        "box": list(box),
                        "type": kind,
                        "score": float(score),
                        "area": box_area(box),
                    }
                    for box, kind, score in detections
                ],
                "outputs": outputs,
            }
        )
        print(f"  -> composite candidate: {len(detections)} people", flush=True)

    result = {
        "upstream": {
            "library": "dghs-imgutils",
            "model_repo": "deepghs/anime_person_detection",
            "model_name": MODEL_NAME,
            "conf_threshold": CONF_THRESHOLD,
            "iou_threshold": IOU_THRESHOLD,
        },
        "dataset": str(folder),
        "scanned": scanned,
        "composite_candidates": len(rows),
        "samples": rows,
    }
    (out / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_contact_sheet(rows, out)

    print("", flush=True)
    print(f"Done: {out}", flush=True)
    print(f"Scanned: {scanned}", flush=True)
    print(f"Composite candidates: {len(rows)}", flush=True)
    print(f"Split images exported: {sum(len(r['outputs']) for r in rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
