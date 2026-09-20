"""Benchmark an existing mature anime-person detector on prior Auto Crop failures.

No crop algorithm is implemented here. The script calls DeepGHS imgutils'
detect_person() and visualizes the raw upstream outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    from imgutils.detect import detect_person
except ImportError as exc:
    raise SystemExit(
        "dghs-imgutils is not installed. Run research\\运行成熟人物检测基线.bat"
    ) from exc

MODEL_NAME = "person_detect_v1.3_s"
CONF_THRESHOLD = 0.3
IOU_THRESHOLD = 0.5
TARGET = 20
FAILURE_LABELS = {"MISSED_CROP", "MANUAL", "TOO_TIGHT"}


def local_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))


def find_latest_review_run() -> Path:
    root = local_root() / "Face LoRA Dataset Selector" / "research" / "auto_crop"
    candidates = []
    if root.exists():
        for labels in root.rglob("review_labels.json"):
            run = labels.parent
            if (run / "review_pack.json").exists():
                candidates.append(run)
    if not candidates:
        raise RuntimeError("没有找到之前完成的 Auto Crop review 结果。")
    return max(candidates, key=lambda p: (p / "review_labels.json").stat().st_mtime)


def load_challenge_paths(run: Path, limit: int) -> list[tuple[Path, str]]:
    pack = json.loads((run / "review_pack.json").read_text(encoding="utf-8"))
    labels = json.loads((run / "review_labels.json").read_text(encoding="utf-8")).get("labels", {})
    selected = []
    for sample in pack.get("samples", []):
        path = Path(sample["path"])
        label = labels.get(sample["path"], "")
        if label in FAILURE_LABELS and path.exists():
            selected.append((path, label))

    def priority(item):
        path, label = item
        p = 0 if label in {"MANUAL", "TOO_TIGHT"} else 1
        stable = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
        return p, stable

    selected.sort(key=priority)
    if not selected:
        raise RuntimeError("Review 中没有找到 MISSED_CROP / MANUAL / TOO_TIGHT 样本。")
    return selected[:limit]


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB").copy()
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def overlay_boxes(image: Image.Image, detections) -> Image.Image:
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    width = max(3, round(min(out.size) * 0.006))
    for idx, (box, kind, score) in enumerate(detections, 1):
        x0, y0, x1, y1 = box
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline="red", width=width)
        draw.text((x0 + 4, max(0, y0 - 16)), f"{idx}:{kind} {score:.3f}", fill="red")
    return out


def top_crop(image: Image.Image, detections) -> Image.Image:
    if not detections:
        return Image.new("RGB", image.size, "white")
    box, _, _ = max(detections, key=lambda x: x[2])
    return image.crop(tuple(box)).convert("RGB")


def make_contact_sheets(rows: list[dict], out: Path) -> None:
    tile_w, tile_h = 460, 420
    cols = 3
    rows_per_page = 4
    for page_no, start in enumerate(range(0, len(rows), rows_per_page), 1):
        batch = rows[start:start + rows_per_page]
        page = Image.new("RGB", (cols * tile_w, len(batch) * tile_h), "white")
        draw = ImageDraw.Draw(page)
        for r, item in enumerate(batch):
            with Image.open(item["path"]) as im:
                im.seek(0)
                original = ImageOps.exif_transpose(im).convert("RGB")
            detections = [
                (tuple(d["box"]), d["type"], d["score"]) for d in item["detections"]
            ]
            visuals = [
                ("ORIGINAL", original),
                ("RAW DEEPGHS BOX", overlay_boxes(original, detections)),
                ("RAW TOP BOX CROP", top_crop(original, detections)),
            ]
            for col, (title, image) in enumerate(visuals):
                x, y = col * tile_w, r * tile_h
                page.paste(fit(image, (tile_w - 16, tile_h - 58)), (x + 8, y + 28))
                draw.text((x + 8, y + 7), title, fill="black")
            draw.text(
                (8, r * tile_h + tile_h - 24),
                f"{Path(item['path']).name[:90]} | old_label={item['old_label']} | detections={len(detections)}",
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
        / "mature_person_v1_3_s"
        / stamp
    )
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"Review source: {review_run}", flush=True)
    print(f"Challenge images: {len(challenge)}", flush=True)
    print(f"Upstream model: {MODEL_NAME}", flush=True)

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
        rows.append(
            {
                "path": str(path),
                "old_label": old_label,
                "detections": [
                    {"box": list(box), "type": kind, "score": float(score)}
                    for box, kind, score in detections
                ],
            }
        )

    no_detection = sum(not r["detections"] for r in rows)
    multi_detection = sum(len(r["detections"]) > 1 for r in rows)
    result = {
        "upstream": {
            "library": "dghs-imgutils",
            "model_repo": "deepghs/anime_person_detection",
            "model_name": MODEL_NAME,
            "conf_threshold": CONF_THRESHOLD,
            "iou_threshold": IOU_THRESHOLD,
        },
        "source_review_run": str(review_run),
        "count": len(rows),
        "no_detection": no_detection,
        "multi_detection": multi_detection,
        "samples": rows,
    }
    (out / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    make_contact_sheets(rows, out)

    print("", flush=True)
    print(f"Done: {out}", flush=True)
    print(f"No detection: {no_detection}/{len(rows)}", flush=True)
    print(f"Multiple detections: {multi_detection}/{len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
