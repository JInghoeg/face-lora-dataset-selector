"""Stage 3: mature-pattern mask -> conservative trim benchmark.

Reuses Stage 2 masks. No model inference and no downloads.

Reference behavior patterns studied:
- Forge: mask bounding box + optional padding.
- ADetailer: mask-derived bbox + configurable padding.

We do not vendor/copy AGPL implementation code. This harness independently
implements the geometry with Pillow and evaluates it on the frozen Stage 2 set.

Research-only adaptation:
ADetailer commonly exposes a 32 px padding default. Because our source images
vary greatly in resolution while ISNetIS uses a canonical 1024 long-side scale,
the padded baseline maps 32 / 1024 of the source long side back to source pixels.
This keeps the research baseline resolution-stable. It is NOT a frozen
production threshold.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE2_ROOT = PROJECT_ROOT / "_research_output" / "auto_crop_stage2"
STAGE3_ROOT = PROJECT_ROOT / "_research_output" / "auto_crop_stage3"

CANONICAL_SCALE = 1024
REFERENCE_PAD_AT_1024 = 32


def _latest_stage2_run() -> Path:
    override = os.environ.get("FACE_LORA_STAGE2_RUN")
    if override:
        run = Path(override).resolve()
    else:
        pointer = STAGE2_ROOT / "latest_run.txt"
        if not pointer.exists():
            raise RuntimeError(
                "找不到 Stage 2 latest_run.txt。请先在同一研究副本完成 Stage 2。"
            )
        run = Path(pointer.read_text(encoding="utf-8").strip()).resolve()

    if not (run / "results.json").exists():
        raise RuntimeError(f"Stage 2 run 缺少 results.json：{run}")
    if not (run / "masks").exists():
        raise RuntimeError(f"Stage 2 run 缺少 masks/：{run}")
    return run


def mask_bbox(mask: Image.Image):
    """Foreground support bbox using every non-zero saved ISNetIS alpha pixel."""
    return mask.convert("L").getbbox()


def canonical_padding(image_size, pad_at_1024=REFERENCE_PAD_AT_1024):
    """Map a reference padding at 1024-long-side back to source pixels."""
    w, h = image_size
    long_side = max(w, h)
    return max(1, int(round(float(pad_at_1024) * long_side / CANONICAL_SCALE)))


def expand_box(box, image_size, pad):
    if box is None:
        return None
    w, h = image_size
    x0, y0, x1, y1 = map(int, box)
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(w, x1 + pad),
        min(h, y1 + pad),
    )


def area(box):
    if box is None:
        return 0
    x0, y0, x1, y1 = box
    return max(0, x1 - x0) * max(0, y1 - y0)


def removed_ratio(box, image_size):
    w, h = image_size
    total = max(1, w * h)
    return 1.0 - area(box) / total


def side_trims(box, image_size):
    if box is None:
        return None
    w, h = image_size
    x0, y0, x1, y1 = box
    return {
        "left": x0,
        "top": y0,
        "right": w - x1,
        "bottom": h - y1,
    }


def touches_source_edge(box, image_size):
    if box is None:
        return True
    w, h = image_size
    x0, y0, x1, y1 = box
    return x0 <= 0 or y0 <= 0 or x1 >= w or y1 >= h


def fit(image, size):
    image = image.convert("RGB").copy()
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(
        image,
        ((size[0] - image.width) // 2, (size[1] - image.height) // 2),
    )
    return canvas


def overlay_box(image, box, label, color):
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    if box is not None:
        x0, y0, x1, y1 = box
        width = max(3, round(min(out.size) * 0.006))
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=color, width=width)
        draw.text((x0 + 5, max(0, y0 - 18)), label, fill=color)
    return out


def make_contact_sheets(rows, out_dir):
    tile_w, tile_h = 330, 360
    cols = 5
    rows_per_page = 4

    for page_no, start in enumerate(range(0, len(rows), rows_per_page), 1):
        batch = rows[start : start + rows_per_page]
        page = Image.new("RGB", (cols * tile_w, len(batch) * tile_h), "white")
        draw = ImageDraw.Draw(page)

        for row_i, row in enumerate(batch):
            source = Image.open(row["path"])
            try:
                source.seek(0)
            except EOFError:
                pass
            source = ImageOps.exif_transpose(source).convert("RGB")

            person = tuple(row["person_box"]) if row["person_box"] else None
            raw = tuple(row["mask_bbox"]) if row["mask_bbox"] else None
            padded = tuple(row["padded_bbox"]) if row["padded_bbox"] else None

            if padded:
                crop = source.crop(padded)
            else:
                crop = source

            visuals = [
                ("ORIGINAL", source),
                ("STAGE1 PERSON BBOX", overlay_box(source, person, "person", "red")),
                ("RAW MASK BBOX", overlay_box(source, raw, "mask", "blue")),
                (
                    f"MASK BBOX + PAD {row['pad_px']}px",
                    overlay_box(source, padded, "safe-trim candidate", "green"),
                ),
                ("PADDED CROP PREVIEW", crop),
            ]

            y = row_i * tile_h
            for col, (title, image) in enumerate(visuals):
                x = col * tile_w
                draw.text((x + 8, y + 7), title, fill="black")
                page.paste(fit(image, (tile_w - 16, tile_h - 62)), (x + 8, y + 28))

            draw.text(
                (8, y + tile_h - 26),
                (
                    f"{Path(row['path']).name[:70]} | "
                    f"remove raw={row['raw_removed_ratio']:.1%} | "
                    f"pad={row['padded_removed_ratio']:.1%} | "
                    f"pad_px={row['pad_px']} | "
                    f"mask_edge={row['mask_touches_edge']}"
                ),
                fill="black",
            )

        page.save(out_dir / f"contact_{page_no:02d}.jpg", quality=92)


def build(stage2_run: Path, out_dir: Path):
    stage2 = json.loads((stage2_run / "results.json").read_text(encoding="utf-8"))
    rows = []

    for index, item in enumerate(stage2.get("samples", []), 1):
        path = Path(item["path"])
        mask_path = stage2_run / "masks" / item["mask_file"]
        if not path.exists():
            raise RuntimeError(f"原图不存在：{path}")
        if not mask_path.exists():
            raise RuntimeError(f"Stage 2 mask 不存在：{mask_path}")

        with Image.open(path) as source:
            try:
                source.seek(0)
            except EOFError:
                pass
            source = ImageOps.exif_transpose(source).convert("RGB")
            image_size = source.size

        with Image.open(mask_path) as mask_image:
            mask = mask_image.convert("L")
            if mask.size != image_size:
                mask = mask.resize(image_size, Image.Resampling.BILINEAR)

        raw = mask_bbox(mask)
        pad_px = canonical_padding(image_size)
        padded = expand_box(raw, image_size, pad_px)

        rows.append(
            {
                "index": index,
                "path": str(path),
                "stage2_mask": str(mask_path),
                "person_box": item.get("primary_box"),
                "mask_bbox": list(raw) if raw else None,
                "padded_bbox": list(padded) if padded else None,
                "pad_reference": {
                    "pad_at_1024": REFERENCE_PAD_AT_1024,
                    "canonical_scale": CANONICAL_SCALE,
                },
                "pad_px": pad_px,
                "raw_removed_ratio": removed_ratio(raw, image_size) if raw else 0.0,
                "padded_removed_ratio": (
                    removed_ratio(padded, image_size) if padded else 0.0
                ),
                "raw_side_trims": side_trims(raw, image_size),
                "padded_side_trims": side_trims(padded, image_size),
                "mask_touches_edge": touches_source_edge(raw, image_size),
            }
        )

    payload = {
        "stage": "auto_crop_stage3_safe_trim_geometry",
        "source_stage2_run": str(stage2_run),
        "decision_scope": "research_candidates_only_no_production_acceptance",
        "references": {
            "pattern": "mask support bbox plus optional padding",
            "forge": "get_crop_region_v2(mask, pad)",
            "adetailer": "mask bbox plus configurable padding",
            "license_note": (
                "Reference implementations are AGPL; no source code is vendored. "
                "Geometry is independently implemented with Pillow."
            ),
        },
        "adaptation": {
            "reason": (
                "source resolutions vary; normalize ADetailer-like 32px padding "
                "to ISNetIS canonical 1024 long-side scale"
            ),
            "pad_at_1024": REFERENCE_PAD_AT_1024,
            "canonical_scale": CANONICAL_SCALE,
            "production_status": "NOT FROZEN",
        },
        "samples": rows,
    }
    (out_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_contact_sheets(rows, out_dir)
    return rows


def self_test():
    mask = Image.new("L", (100, 80), 0)
    ImageDraw.Draw(mask).rectangle((20, 10, 69, 59), fill=255)
    box = mask_bbox(mask)
    if box != (20, 10, 70, 60):
        raise RuntimeError(f"mask bbox self-test failed: {box}")
    padded = expand_box(box, mask.size, 8)
    if padded != (12, 2, 78, 68):
        raise RuntimeError(f"padding self-test failed: {padded}")
    if not math.isclose(removed_ratio((0, 0, 100, 80), (100, 80)), 0.0):
        raise RuntimeError("removed ratio self-test failed")
    print("Stage 3 geometry self-test OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    stage2_run = _latest_stage2_run()
    out_dir = STAGE3_ROOT / "runs" / stage2_run.name
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build(stage2_run, out_dir)

    STAGE3_ROOT.mkdir(parents=True, exist_ok=True)
    (STAGE3_ROOT / "latest_run.txt").write_text(str(out_dir), encoding="utf-8")

    print(f"Stage 2 source: {stage2_run}")
    print(f"Stage 3 output: {out_dir}")
    print(f"Samples: {len(rows)}")
    print("No model inference was run. Existing Stage 2 masks were reused.")
    print("No production crop policy was frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
