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

PRIMARY_ALPHA_MIN = 0.10
DIAGNOSTIC_ALPHA_MIN = 0.20
FIXED_PADDING_PX = 32


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
    """Raw soft-mask support bbox; diagnostic only."""
    return mask.convert("L").getbbox()


def thresholded_mask(mask: Image.Image, alpha_min: float) -> Image.Image:
    """Drop low-confidence soft-alpha responses before bbox extraction."""
    threshold = max(0, min(255, int(math.ceil(float(alpha_min) * 255.0))))
    lut = [0 if value < threshold else 255 for value in range(256)]
    return mask.convert("L").point(lut)


def thresholded_bbox(mask: Image.Image, alpha_min: float):
    return thresholded_mask(mask, alpha_min).getbbox()


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
    tile_w, tile_h = 300, 350
    cols = 6
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
            raw = tuple(row["raw_mask_bbox"]) if row["raw_mask_bbox"] else None
            primary = tuple(row["primary_bbox"]) if row["primary_bbox"] else None
            diagnostic = tuple(row["diagnostic_bbox"]) if row["diagnostic_bbox"] else None
            padded = tuple(row["primary_padded_bbox"]) if row["primary_padded_bbox"] else None

            crop = source.crop(padded) if padded else source

            visuals = [
                ("ORIGINAL", source),
                ("STAGE1 PERSON BBOX", overlay_box(source, person, "person", "red")),
                ("RAW SOFT MASK BBOX", overlay_box(source, raw, "raw", "blue")),
                (
                    "ALPHA>=0.10 + PAD32",
                    overlay_box(source, padded, "primary", "green"),
                ),
                (
                    "ALPHA>=0.20 + PAD32",
                    overlay_box(
                        source,
                        expand_box(diagnostic, source.size, FIXED_PADDING_PX)
                        if diagnostic else None,
                        "diagnostic",
                        "orange",
                    ),
                ),
                ("PRIMARY CROP PREVIEW", crop),
            ]

            y = row_i * tile_h
            for col, (title, image) in enumerate(visuals):
                x = col * tile_w
                draw.text((x + 8, y + 7), title, fill="black")
                page.paste(fit(image, (tile_w - 16, tile_h - 62)), (x + 8, y + 28))

            draw.text(
                (8, y + tile_h - 26),
                (
                    f"{Path(row['path']).name[:62]} | "
                    f"raw={row['raw_removed_ratio']:.1%} | "
                    f"a0.10+32={row['primary_removed_ratio']:.1%} | "
                    f"a0.20+32={row['diagnostic_removed_ratio']:.1%} | "
                    f"edge0.10={row['primary_touches_edge']}"
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
        primary = thresholded_bbox(mask, PRIMARY_ALPHA_MIN)
        diagnostic = thresholded_bbox(mask, DIAGNOSTIC_ALPHA_MIN)
        primary_padded = expand_box(primary, image_size, FIXED_PADDING_PX)
        diagnostic_padded = expand_box(diagnostic, image_size, FIXED_PADDING_PX)

        rows.append(
            {
                "index": index,
                "path": str(path),
                "stage2_mask": str(mask_path),
                "person_box": item.get("primary_box"),
                "raw_mask_bbox": list(raw) if raw else None,
                "primary_alpha_min": PRIMARY_ALPHA_MIN,
                "primary_bbox": list(primary) if primary else None,
                "primary_padded_bbox": list(primary_padded) if primary_padded else None,
                "diagnostic_alpha_min": DIAGNOSTIC_ALPHA_MIN,
                "diagnostic_bbox": list(diagnostic) if diagnostic else None,
                "diagnostic_padded_bbox": list(diagnostic_padded) if diagnostic_padded else None,
                "padding_px": FIXED_PADDING_PX,
                "raw_removed_ratio": removed_ratio(raw, image_size) if raw else 0.0,
                "primary_removed_ratio": (
                    removed_ratio(primary_padded, image_size)
                    if primary_padded else 0.0
                ),
                "diagnostic_removed_ratio": (
                    removed_ratio(diagnostic_padded, image_size)
                    if diagnostic_padded else 0.0
                ),
                "raw_side_trims": side_trims(raw, image_size),
                "primary_side_trims": side_trims(primary_padded, image_size),
                "diagnostic_side_trims": side_trims(diagnostic_padded, image_size),
                "raw_touches_edge": touches_source_edge(raw, image_size),
                "primary_touches_edge": touches_source_edge(primary, image_size),
                "diagnostic_touches_edge": touches_source_edge(diagnostic, image_size),
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
                "ISNetIS returns soft alpha. Stage 3.1 drops weak responses before "
                "bbox extraction and returns to mature fixed-pixel bbox padding."
            ),
            "primary_alpha_min": PRIMARY_ALPHA_MIN,
            "diagnostic_alpha_min": DIAGNOSTIC_ALPHA_MIN,
            "fixed_padding_px": FIXED_PADDING_PX,
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
    soft = Image.new("L", (100, 80), 5)
    ImageDraw.Draw(soft).rectangle((20, 10, 69, 59), fill=255)
    primary = thresholded_bbox(soft, 0.10)
    if primary != (20, 10, 70, 60):
        raise RuntimeError(f"alpha-floor bbox self-test failed: {primary}")
    padded = expand_box(primary, soft.size, 8)
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
    print("Stage 3.1 primary geometry: alpha>=0.10 support + fixed 32px padding.")
    print("Stage 3.1 diagnostic geometry: alpha>=0.20 support + fixed 32px padding.")
    print("No production crop policy was frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
