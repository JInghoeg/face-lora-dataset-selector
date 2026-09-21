"""Validate mature ISNetIS masks on the frozen Auto Crop challenge set.

Stage 2 is intentionally mask validation only:
- reuse DeepGHS person detection;
- reuse imgutils.segment.get_isnetis_mask;
- save raw mask/cutout/contact sheets;
- do NOT derive a crop;
- do NOT invent margin/saliency/pose heuristics.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:
    from imgutils.detect import detect_person
    from imgutils.segment import get_isnetis_mask
except ImportError as exc:
    raise SystemExit(
        "缺少 dghs-imgutils。请运行 research\\运行AutoCrop Stage2 ISNetIS.bat"
    ) from exc

from auto_crop_stage2_common import (
    TARGET,
    fit,
    freeze_or_load_challenge,
    overlay_boxes,
    primary_detection,
    research_root,
)

MODEL_NAME = "person_detect_v1.3_s"
CONF_THRESHOLD = 0.3
IOU_THRESHOLD = 0.5


def mask_visual(mask: np.ndarray) -> Image.Image:
    arr = np.clip(mask, 0.0, 1.0)
    arr = (arr * 255.0).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def make_contact_sheets(rows: list[dict], out: Path) -> None:
    tile_w, tile_h = 360, 390
    cols = 4
    rows_per_page = 4
    masks_dir = out / "masks"

    for page_no, start in enumerate(
        range(0, len(rows), rows_per_page), 1
    ):
        batch = rows[start : start + rows_per_page]
        page = Image.new(
            "RGB",
            (cols * tile_w, len(batch) * tile_h),
            "white",
        )
        draw = ImageDraw.Draw(page)

        for row_index, item in enumerate(batch):
            with Image.open(item["path"]) as source:
                try:
                    source.seek(0)
                except EOFError:
                    pass
                original = ImageOps.exif_transpose(source).convert("RGB")

            with Image.open(masks_dir / item["mask_file"]) as mask_image:
                mask = (
                    np.asarray(mask_image.convert("L"), dtype=np.float32)
                    / 255.0
                )

            detections = [
                (tuple(d["box"]), d["type"], d["score"])
                for d in item["detections"]
            ]

            alpha = Image.fromarray(
                (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8),
                mode="L",
            )
            cutout = Image.new(
                "RGBA", original.size, (255, 255, 255, 0)
            )
            cutout.paste(original.convert("RGBA"), (0, 0), alpha)

            visuals = [
                ("ORIGINAL", original),
                (
                    "PERSON DETECTIONS",
                    overlay_boxes(original, detections),
                ),
                ("RAW ISNETIS MASK", mask_visual(mask)),
                ("ISNETIS CUTOUT", cutout),
            ]

            for col, (title, image) in enumerate(visuals):
                x = col * tile_w
                y = row_index * tile_h
                if image.mode == "RGBA":
                    bg = Image.new(
                        "RGBA", image.size, (255, 255, 255, 255)
                    )
                    bg.alpha_composite(image)
                    image = bg.convert("RGB")
                page.paste(
                    fit(image, (tile_w - 16, tile_h - 58)),
                    (x + 8, y + 28),
                )
                draw.text((x + 8, y + 7), title, fill="black")

            draw.text(
                (8, row_index * tile_h + tile_h - 24),
                (
                    f"{Path(item['path']).name[:80]} | "
                    f"old_label={item['old_label']} | "
                    f"detections={len(detections)} | "
                    f"ambiguous={item['ambiguous_multi_person']}"
                ),
                fill="black",
            )

        page.save(out / f"contact_{page_no:02d}.jpg", quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-challenge",
        action="store_true",
        help="Explicitly rebuild the frozen 20-image challenge manifest.",
    )
    args = parser.parse_args()

    manifest, challenge = freeze_or_load_challenge(
        TARGET,
        refresh=args.refresh_challenge,
    )

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = research_root() / "runs" / stamp
    masks_dir = out / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"Frozen challenge manifest: {manifest}", flush=True)
    print(f"Challenge images: {len(challenge)}", flush=True)
    print(
        "Upstream segmentation: imgutils.segment.get_isnetis_mask",
        flush=True,
    )
    print(f"Output: {out}", flush=True)

    for index, (path, old_label) in enumerate(challenge, 1):
        print(
            f"[{index}/{len(challenge)}] {path.name}",
            flush=True,
        )
        with Image.open(path) as source:
            try:
                source.seek(0)
            except EOFError:
                pass
            image = ImageOps.exif_transpose(source).convert("RGB")

        detections = detect_person(
            image,
            model_name=MODEL_NAME,
            conf_threshold=CONF_THRESHOLD,
            iou_threshold=IOU_THRESHOLD,
        )
        primary, ambiguous = primary_detection(detections)

        mask = get_isnetis_mask(image)
        mask_name = f"{index:02d}_{path.stem[:80]}.png"
        Image.fromarray(
            (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8),
            mode="L",
        ).save(masks_dir / mask_name)

        rows.append(
            {
                "path": str(path),
                "old_label": old_label,
                "detections": [
                    {
                        "box": list(box),
                        "type": kind,
                        "score": float(score),
                    }
                    for box, kind, score in detections
                ],
                "primary_policy": "largest_area_review_only",
                "primary_box": list(primary[0]) if primary else None,
                "ambiguous_multi_person": ambiguous,
                "mask_file": mask_name,
            }
        )

    result = {
        "stage": "auto_crop_stage2_isnetis_mask_validation",
        "decision_scope": "raw_mask_only_no_crop_derivation",
        "challenge_manifest": str(manifest),
        "count": len(rows),
        "upstream_person": {
            "library": "dghs-imgutils==0.19.0",
            "model_repo": "deepghs/anime_person_detection",
            "model_name": MODEL_NAME,
            "conf_threshold": CONF_THRESHOLD,
            "iou_threshold": IOU_THRESHOLD,
        },
        "upstream_segmentation": {
            "library": "dghs-imgutils==0.19.0",
            "api": "imgutils.segment.get_isnetis_mask",
            "model_repo": "skytnt/anime-seg",
            "model": "isnetis.onnx",
            "scale": 1024,
        },
        "samples": rows,
    }
    (out / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_contact_sheets(rows, out)

    latest = research_root() / "latest_run.txt"
    latest.write_text(str(out), encoding="utf-8")

    print("", flush=True)
    print(f"Done: {out}", flush=True)
    print(
        "Next gate: inspect the 5 contact sheets for "
        "hair/hands/feet/clothing/weapons/props/accessories.",
        flush=True,
    )
    print(
        "No crop rectangle was derived in this stage.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
