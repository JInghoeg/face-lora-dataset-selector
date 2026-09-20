"""CI parity check between vendored DeepGHS YOLO path and official imgutils."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image

PERSON_MODEL = "person_detect_v1.3_s"
HEAD_MODEL = "head_detect_v2.0_s"


def serialize(items):
    return [
        {"box": list(map(int, box)), "kind": str(kind), "score": float(score)}
        for box, kind, score in items
    ]


def run_vendor(image_path: Path, output: Path):
    from deepghs_yolo_runtime import detect_heads, detect_person

    image = Image.open(image_path).convert("RGB")
    cache = Path("_parity_vendor_models")
    result = {
        "person": serialize(
            detect_person(
                image,
                model_cache=cache,
                model_name=PERSON_MODEL,
                conf_threshold=0.3,
                iou_threshold=0.5,
            )
        ),
        "head": serialize(
            detect_heads(
                image,
                model_cache=cache,
                model_name=HEAD_MODEL,
                conf_threshold=0.4,
                iou_threshold=0.7,
            )
        ),
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


def run_official(image_path: Path, output: Path):
    from imgutils.detect import detect_heads, detect_person

    image = Image.open(image_path).convert("RGB")
    result = {
        "person": serialize(
            detect_person(
                image,
                model_name=PERSON_MODEL,
                conf_threshold=0.3,
                iou_threshold=0.5,
            )
        ),
        "head": serialize(
            detect_heads(
                image,
                model_name=HEAD_MODEL,
                conf_threshold=0.4,
                iou_threshold=0.7,
            )
        ),
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


def sort_key(item):
    box = item["box"]
    return (item["kind"], box[0], box[1], box[2], box[3])


def compare_group(name, actual, expected):
    actual = sorted(actual, key=sort_key)
    expected = sorted(expected, key=sort_key)
    if len(actual) != len(expected):
        raise AssertionError(
            f"{name}: detection count differs: vendor={len(actual)}, official={len(expected)}"
        )

    for index, (left, right) in enumerate(zip(actual, expected), 1):
        if left["kind"] != right["kind"]:
            raise AssertionError(
                f"{name} #{index}: kind differs: {left['kind']} != {right['kind']}"
            )
        diffs = [abs(int(a) - int(b)) for a, b in zip(left["box"], right["box"])]
        if max(diffs, default=0) > 1:
            raise AssertionError(
                f"{name} #{index}: bbox differs: {left['box']} != {right['box']}"
            )
        if abs(float(left["score"]) - float(right["score"])) > 1e-5:
            raise AssertionError(
                f"{name} #{index}: confidence differs: "
                f"{left['score']} != {right['score']}"
            )


def compare(vendor_path: Path, official_path: Path):
    vendor = json.loads(vendor_path.read_text(encoding="utf-8"))
    official = json.loads(official_path.read_text(encoding="utf-8"))
    compare_group("person", vendor["person"], official["person"])
    compare_group("head", vendor["head"], official["head"])
    print(
        "DeepGHS parity OK: "
        f"person={len(vendor['person'])}, head={len(vendor['head'])}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("vendor", "official", "compare"))
    parser.add_argument("--image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--vendor", type=Path)
    parser.add_argument("--official", type=Path)
    args = parser.parse_args()

    if args.mode == "vendor":
        run_vendor(args.image, args.output)
    elif args.mode == "official":
        run_official(args.image, args.output)
    else:
        compare(args.vendor, args.official)


if __name__ == "__main__":
    main()
