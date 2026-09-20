"""Benchmark the existing ISNetIS anime-character segmentation on the same failures.

This script does not derive a crop or invent segmentation logic. It calls the
upstream DeepGHS imgutils implementation, saves the raw mask, and builds review
sheets beside the mature person detector result.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:
    from imgutils.detect import detect_person
    from imgutils.segment import get_isnetis_mask
except ImportError as exc:
    raise SystemExit(
        "dghs-imgutils is not installed. Run research\\运行成熟人物检测基线.bat first."
    ) from exc

from mature_person_benchmark import (
    CONF_THRESHOLD,
    IOU_THRESHOLD,
    MODEL_NAME,
    TARGET,
    find_latest_review_run,
    fit,
    load_challenge_paths,
    overlay_boxes,
    primary_detection,
)


def local_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))


def mask_visual(mask: np.ndarray) -> Image.Image:
    arr = np.clip(mask, 0.0, 1.0)
    arr = (arr * 255.0).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def overlay_mask(image: Image.Image, mask: np.ndarray) -> Image.Image:
    base = image.convert("RGBA")
    alpha = Image.fromarray(
        (np.clip(mask, 0.0, 1.0) * 150.0).astype(np.uint8), mode="L"
    )
    tint = Image.new("RGBA", image.size, (255, 0, 0, 0))
    tint.putalpha(alpha)
    return Image.alpha_composite(base, tint).convert("RGB")


def make_contact_sheets(rows: list[dict], out: Path) -> None:
    tile_w, tile_h = 360, 390
    cols = 4
    rows_per_page = 4
    masks_dir = out / "masks"
    masks_dir.mkdir(exist_ok=True)

    for page_no, start in enumerate(range(0, len(rows), rows_per_page), 1):
        batch = rows[start:start + rows_per_page]
        page = Image.new("RGB", (cols * tile_w, len(batch) * tile_h), "white")
        draw = ImageDraw.Draw(page)

        for r, item in enumerate(batch):
            with Image.open(item["path"]) as im:
                im.seek(0)
                original = ImageOps.exif_transpose(im).convert("RGB")

            mask_path = masks_dir / item["mask_file"]
            with Image.open(mask_path) as mm:
                mask_img = mm.convert("L")
            mask = np.asarray(mask_img, dtype=np.float32) / 255.0

            detections = [
                (tuple(d["box"]), d["type"], d["score"])
                for d in item["detections"]
            ]
            alpha = Image.fromarray(
                (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L"
            )
            cutout = Image.new("RGBA", original.size, (255, 255, 255, 0))
            cutout.paste(original.convert("RGBA"), (0, 0), alpha)

            visuals = [
                ("ORIGINAL", original),
                ("PERSON DETECTIONS", overlay_boxes(original, detections)),
                ("RAW ISNETIS MASK", mask_visual(mask)),
                ("ISNETIS CUTOUT", cutout),
            ]
            for col, (title, image) in enumerate(visuals):
                x, y = col * tile_w, r * tile_h
                if image.mode == "RGBA":
                    bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
                    bg.alpha_composite(image)
                    image = bg.convert("RGB")
                page.paste(fit(image, (tile_w - 16, tile_h - 58)), (x + 8, y + 28))
                draw.text((x + 8, y + 7), title, fill="black")

            draw.text(
                (8, r * tile_h + tile_h - 24),
                f"{Path(item['path']).name[:80]} | old_label={item['old_label']} | "
                f"detections={len(detections)} | ambiguous={item['ambiguous_multi_person']}",
                fill="black",
            )

        page.save(out / f"contact_{page_no:02d}.jpg", quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=TARGET)
    args = parser.parse_args()

    review_run = find_latest_review_run()
    challenge = load_challenge_paths(review_run, args.limit)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = (
        local_root()
        / "Face LoRA Dataset Selector"
        / "research"
        / "mature_isnetis"
        / stamp
    )
    out.mkdir(parents=True, exist_ok=True)
    masks_dir = out / "masks"
    masks_dir.mkdir(exist_ok=True)

    rows = []
    print(f"Review source: {review_run}", flush=True)
    print(f"Challenge images: {len(challenge)}", flush=True)
    print("Upstream segmentation: imgutils.segment.get_isnetis_mask", flush=True)

    for i, (path, old_label) in enumerate(challenge, 1):
        print(f"[{i}/{len(challenge)}] {path.name}", flush=True)
        with Image.open(path) as im:
            im.seek(0)
            image = ImageOps.exif_transpose(im).convert("RGB")

        detections = detect_person(
            image,
            model_name=MODEL_NAME,
            conf_threshold=CONF_THRESHOLD,
            iou_threshold=IOU_THRESHOLD,
        )
        primary, ambiguous = primary_detection(detections)

        mask = get_isnetis_mask(image)
        mask_name = f"{i:02d}_{path.stem[:80]}.png"
        Image.fromarray(
            (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L"
        ).save(masks_dir / mask_name)

        rows.append(
            {
                "path": str(path),
                "old_label": old_label,
                "detections": [
                    {"box": list(box), "type": kind, "score": float(score)}
                    for box, kind, score in detections
                ],
                "primary_policy": "largest_area",
                "primary_box": list(primary[0]) if primary else None,
                "ambiguous_multi_person": ambiguous,
                "mask_file": mask_name,
            }
        )

    result = {
        "upstream_person": {
            "library": "dghs-imgutils",
            "model_repo": "deepghs/anime_person_detection",
            "model_name": MODEL_NAME,
        },
        "upstream_segmentation": {
            "library": "dghs-imgutils",
            "api": "imgutils.segment.get_isnetis_mask",
            "model_repo": "skytnt/anime-seg",
            "model": "isnetis.onnx",
            "scale": 1024,
        },
        "source_review_run": str(review_run),
        "count": len(rows),
        "samples": rows,
    }
    (out / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    make_contact_sheets(rows, out)

    print("", flush=True)
    print(f"Done: {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
