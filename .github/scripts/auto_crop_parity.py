from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def vendor(image_path: Path, cache: Path, out: Path, model_path_file: Path):
    from features.auto_crop.runtime import ISNETIS_SPEC, get_isnetis_mask
    from infrastructure.model_download import ensure_model

    model = ensure_model(ISNETIS_SPEC, cache)
    image = Image.open(image_path).convert("RGB")
    mask = get_isnetis_mask(image, cache)
    np.save(out, mask)
    model_path_file.write_text(str(model.resolve()), encoding="utf-8")
    print(f"vendor mask: shape={mask.shape} min={mask.min():.8f} max={mask.max():.8f}")
    print(f"model: {model}")


def official(image_path: Path, model_path: Path, out: Path):
    from imgutils.segment import isnetis
    from imgutils.utils.onnxruntime import open_onnx_model

    session = open_onnx_model(str(model_path))
    isnetis._get_model = lambda: session
    mask = isnetis.get_isnetis_mask(str(image_path), scale=1024)
    np.save(out, mask)
    print(f"official mask: shape={mask.shape} min={mask.min():.8f} max={mask.max():.8f}")


def compare(vendor_path: Path, official_path: Path):
    left = np.load(vendor_path)
    right = np.load(official_path)
    if left.shape != right.shape:
        raise SystemExit(f"shape mismatch: {left.shape} != {right.shape}")
    diff = np.abs(left.astype(np.float64) - right.astype(np.float64))
    mean = float(diff.mean())
    max_diff = float(diff.max())
    print(f"parity: mean_abs={mean:.10g} max_abs={max_diff:.10g}")
    if mean > 1e-6 or max_diff > 1e-4:
        raise SystemExit(
            f"ISNetIS parity failed: mean_abs={mean}, max_abs={max_diff}"
        )
    print("ISNetIS production runtime parity PASS")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("vendor")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model-path-file", type=Path, required=True)

    p = sub.add_parser("official")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("compare")
    p.add_argument("--vendor", type=Path, required=True)
    p.add_argument("--official", type=Path, required=True)

    args = parser.parse_args()
    if args.mode == "vendor":
        vendor(args.image, args.cache, args.out, args.model_path_file)
    elif args.mode == "official":
        official(args.image, args.model, args.out)
    else:
        compare(args.vendor, args.official)


if __name__ == "__main__":
    main()
