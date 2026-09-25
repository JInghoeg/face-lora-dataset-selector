#!/usr/bin/env python
"""Research-only provider benchmark for Face LoRA Dataset Selector.

The script does not alter production dependencies or provider defaults. Run CPU
and CUDA in separate environments/processes, then compare their JSON reports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

STAGES = ("ranking", "auto_crop", "composite", "text_scan", "migan")


def sig(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except Exception:
        return str(path)


def snapshot(roots):
    out = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    st = path.stat()
                    out[str(path.resolve()).casefold()] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    pass
    return out


class NvidiaSampler:
    """Best-effort device-level telemetry; other GPU apps can affect values."""
    def __init__(self, period=0.5):
        self.period = period
        self.samples = []
        self.error = None
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if shutil.which("nvidia-smi") is None:
            self.error = "nvidia-smi not found"
            return

        def worker():
            while not self.stop_event.is_set():
                try:
                    cp = subprocess.run(
                        ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                        check=True, capture_output=True, text=True, timeout=5,
                    )
                    first = cp.stdout.strip().splitlines()[0]
                    util, mem = [x.strip() for x in first.split(",")[:2]]
                    self.samples.append((float(util), float(mem)))
                except Exception as exc:
                    self.error = f"{type(exc).__name__}: {exc}"
                    return
                self.stop_event.wait(self.period)

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def summary(self):
        if not self.samples:
            return {"available": False, "error": self.error}
        utils = [x[0] for x in self.samples]
        mem = [x[1] for x in self.samples]
        return {
            "available": True,
            "samples": len(self.samples),
            "gpu_util_avg_percent": round(statistics.fmean(utils), 2),
            "gpu_util_max_percent": round(max(utils), 2),
            "device_memory_min_mib": round(min(mem), 1),
            "device_memory_max_mib": round(max(mem), 1),
            "device_memory_delta_mib": round(max(mem) - min(mem), 1),
            "note": "device-level telemetry; other GPU applications can affect it",
        }


def install_provider_override(provider):
    import onnxruntime as ort

    requested = ["CPUExecutionProvider"] if provider == "cpu" else ["CUDAExecutionProvider", "CPUExecutionProvider"]
    available = list(ort.get_available_providers())
    if provider == "cuda" and "CUDAExecutionProvider" not in available:
        raise RuntimeError(f"CUDAExecutionProvider unavailable; available={available!r}")

    preload = None
    if provider == "cuda" and hasattr(ort, "preload_dlls"):
        try:
            ort.preload_dlls()
            preload = "ok"
        except Exception as exc:
            preload = f"{type(exc).__name__}: {exc}"

    real_session = ort.InferenceSession
    sessions = []

    def patched(path_or_bytes, *args, **kwargs):
        kwargs["providers"] = list(requested)
        session = real_session(path_or_bytes, *args, **kwargs)
        sessions.append({
            "model": str(path_or_bytes),
            "requested": list(requested),
            "actual": list(session.get_providers()),
        })
        return session

    ort.InferenceSession = patched
    return sessions, {
        "provider": provider,
        "provider_order": requested,
        "available_providers": available,
        "onnxruntime_version": getattr(ort, "__version__", "unknown"),
        "onnxruntime_module": str(getattr(ort, "__file__", "")),
        "preload_dlls": preload,
    }


def measure(name, fn, roots, sessions):
    before = snapshot(roots)
    session_start = len(sessions)
    sampler = NvidiaSampler()
    sampler.start()
    t0, c0 = time.perf_counter(), time.process_time()
    payload = None
    error = None
    try:
        payload = fn()
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    cpu = time.process_time() - c0
    wall = time.perf_counter() - t0
    sampler.stop()
    changed = before != snapshot(roots)
    result = {
        "stage": name,
        "status": "error" if error else "ok",
        "wall_seconds": round(wall, 6),
        "cpu_seconds": round(cpu, 6),
        "avg_process_cpu_core_equivalents": round(cpu / wall, 3) if wall else None,
        "gpu": sampler.summary(),
        "model_cache_changed_during_timing": changed,
        "onnx_sessions": sessions[session_start:],
    }
    if payload is not None:
        signature_data = payload.pop("_signature", payload)
        result["signature_sha256"] = sig(signature_data)
        result["result"] = payload
    if changed:
        result["warning"] = "Model cache changed during timing; prime caches and rerun for a fair provider comparison."
    if error:
        result["error"] = error
    return result


def run(args):
    repo = Path(args.repo_root).resolve()
    src = repo / "src"
    if not src.is_dir():
        raise SystemExit(f"src/ not found under {repo}")
    sys.path.insert(0, str(src))
    dataset = Path(args.dataset).resolve()
    if not dataset.is_dir():
        raise SystemExit(f"Dataset does not exist: {dataset}")

    sessions, provider = install_provider_override(args.provider)

    from core.models import TextPhoto
    from features.auto_crop.service import detect_proposal as auto_detect
    from features.composite.proposal import detect_proposal as composite_detect
    from features.ranking.analysis import AnalysisEngine
    from features.text_cleanup.detector import TextDetector
    from features.text_cleanup.service import AI_METHOD, TextCleanupService, _detected, detector_config, suggest
    from infrastructure.filesystem import IMAGE_EXTENSIONS

    resources = repo / "resources"
    model_cache = Path(args.model_cache or os.environ.get("FACE_LORA_MODEL_CACHE_ROOT") or repo.parent / "_FaceLoRA_ModelCache").resolve()
    shared_cache = model_cache.parent / "_shared_cache" / "face-lora-dataset-selector"
    roots = [resources / "models", model_cache, shared_cache]
    auto_cache = model_cache / "auto_crop"
    text_cache = model_cache / "text_cleanup"
    composite_cache = resources / "models" / "composite_split_cache"
    ocr_model = resources / "models" / "ppocrv5_mobile_det" / "inference.onnx"

    files = sorted(
        [p for p in dataset.rglob("*") if p.is_file() and p.suffix.lower() in set(IMAGE_EXTENSIONS)],
        key=lambda p: str(p).casefold(),
    )
    if args.limit > 0:
        files = files[: args.limit]
    if not files:
        raise SystemExit("No supported images found.")

    wanted = [x.strip() for x in args.stages.split(",") if x.strip()]
    unknown = sorted(set(wanted) - set(STAGES))
    if unknown:
        raise SystemExit(f"Unknown stages: {unknown}")

    ctx = {}
    results = []

    if "ranking" in wanted:
        def ranking():
            signature = []
            with AnalysisEngine() as engine:
                for path in files:
                    st = path.stat()
                    r = engine.analyze_one(path, st.st_size, st.st_mtime_ns)
                    signature.append({
                        "path": rel(path, dataset), "faces": r.faces,
                        "quality": round(float(r.face_quality), 6),
                        "brisque": round(float(r.brisque), 4), "blur": round(float(r.blur), 4),
                        "yaw": round(float(r.yaw), 4), "pitch": round(float(r.pitch), 4),
                        "scale": str(r.person_scale), "eligibility": str(r.eligibility),
                    })
            return {"images": len(files), "_signature": signature}
        results.append(measure("ranking", ranking, roots, sessions))

    if "auto_crop" in wanted:
        def auto_crop():
            signature = []
            for path in files:
                p = auto_detect(path, auto_cache)
                signature.append({
                    "path": rel(path, dataset),
                    "box": list(p.box) if p else None,
                    "removed": round(float(p.removed_area_ratio), 8) if p else None,
                })
            return {"images": len(files), "candidates": sum(x["box"] is not None for x in signature), "_signature": signature}
        results.append(measure("auto_crop", auto_crop, roots, sessions))

    if "composite" in wanted:
        def composite():
            from PIL import Image, ImageOps
            signature = []
            for path in files:
                with Image.open(path) as source:
                    try:
                        source.seek(0)
                    except EOFError:
                        pass
                    image = ImageOps.exif_transpose(source).convert("RGB")
                p = composite_detect(image, composite_cache)
                signature.append({
                    "path": rel(path, dataset), "mode": p.mode if p else None,
                    "boxes": [list(map(int, x)) for x in p.output_boxes] if p else [],
                })
            return {"images": len(files), "proposals": sum(x["mode"] is not None for x in signature), "_signature": signature}
        results.append(measure("composite", composite, roots, sessions))

    if "text_scan" in wanted:
        def text_scan():
            if not ocr_model.exists():
                raise FileNotFoundError(f"OCR model missing: {ocr_model}")
            service = TextCleanupService(
                ocr_model_path=ocr_model,
                state_path=Path(tempfile.gettempdir()) / "face-lora-gpu-benchmark" / "subtitle_cleaner.json",
                model_cache=text_cache,
                model_reuse_roots=(resources / "models", shared_cache),
            )
            detector = TextDetector(detector_config(ocr_model))
            records, signature = [], []
            for path in files:
                image = service.load_image(path)
                st = path.stat()
                boxes, scores = ([], []) if image is None else _detected(detector, image)
                h, w = image.shape[:2] if image is not None else (0, 0)
                record = TextPhoto(path, st.st_size, st.st_mtime_ns, boxes, [False] * len(boxes), [False] * len(boxes), scores, [], w, h)
                records.append(record)
                signature.append({"path": rel(path, dataset), "boxes": boxes, "scores": [round(float(x), 7) for x in scores]})
            suggest(records, records)
            ctx["text_service"], ctx["text_records"] = service, records
            return {
                "images": len(files),
                "detections": sum(len(r.boxes) for r in records),
                "suggested_repairs": sum(sum(bool(x) for x in r.suggested) for r in records),
                "_signature": signature,
            }
        results.append(measure("text_scan", text_scan, roots, sessions))

    if "migan" in wanted:
        def migan():
            service, records = ctx.get("text_service"), ctx.get("text_records")
            if service is None or records is None:
                raise RuntimeError("MI-GAN stage requires text_scan in the same run.")
            targets = []
            for record in records:
                if not record.boxes:
                    continue
                if not any(record.selected):
                    record.selected = [True] + [False] * (len(record.boxes) - 1)
                targets.append(record)
                if len(targets) >= args.migan_limit:
                    break
            if not targets:
                return {"images": 0, "note": "No OCR boxes; MI-GAN skipped.", "_signature": []}
            cached = service.migan_ready()
            signature = []
            for record in targets:
                image = service.repair_record(record, method=AI_METHOD, expand=5, radius=4)
                signature.append({
                    "path": rel(record.path, dataset),
                    "shape": list(image.shape) if image is not None else None,
                    "sha256": hashlib.sha256(image.tobytes()).hexdigest() if image is not None else None,
                })
            return {"images": len(targets), "model_cached_before_stage": bool(cached), "_signature": signature}
        results.append(measure("migan", migan, roots, sessions))

    report = {
        "schema_version": 1,
        "kind": "face-lora-gpu-runtime-benchmark",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "platform": platform.platform(), "python": sys.version, "executable": sys.executable,
            **provider,
        },
        "inputs": {
            "repo_root": str(repo), "dataset": str(dataset), "images_selected": len(files),
            "limit": args.limit, "stages": wanted, "model_cache_root": str(model_cache),
        },
        "stages": results,
        "notes": [
            "Compare providers with the same Python version and same files.",
            "If model_cache_changed_during_timing is true, prime caches and rerun.",
            "GPU telemetry is device-level and can include unrelated applications.",
            "The provider override exists only inside this research process; production defaults are unchanged.",
            "Qt responsiveness is not directly measured; only proceed to an in-app spike if command-line gains are material.",
        ],
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {output}")
    print(f"Provider={args.provider} ORT={provider['onnxruntime_version']} images={len(files)}")
    for row in results:
        print(f"{row['stage']:12} {row['status']:5} wall={row['wall_seconds']:.3f}s cpu={row['cpu_seconds']:.3f}s")
    return 0


def compare(args):
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    a = {x["stage"]: x for x in baseline.get("stages", [])}
    b = {x["stage"]: x for x in candidate.get("stages", [])}
    print(f"Baseline={baseline.get('environment', {}).get('provider')} Candidate={candidate.get('environment', {}).get('provider')}")
    print(f"{'stage':12} {'base':>10} {'candidate':>10} {'speedup':>9} {'parity':>8} {'cache':>8}")
    for name in [x["stage"] for x in baseline.get("stages", []) if x["stage"] in b]:
        x, y = a[name], b[name]
        speed = x.get("wall_seconds", 0) / y.get("wall_seconds", 1) if x.get("status") == y.get("status") == "ok" and y.get("wall_seconds", 0) else None
        parity = x.get("signature_sha256") == y.get("signature_sha256") if x.get("signature_sha256") and y.get("signature_sha256") else None
        clean = not (x.get("model_cache_changed_during_timing") or y.get("model_cache_changed_during_timing"))
        speed_text = f"{speed:.2f}x" if speed is not None else "n/a"
        print(f"{name:12} {x.get('wall_seconds', 0):10.3f} {y.get('wall_seconds', 0):10.3f} {speed_text:>9} {str(parity):>8} {str(clean):>8}")
    return 0


def parser():
    p = argparse.ArgumentParser(description="Research-only CPU/CUDA benchmark for Face LoRA Dataset Selector")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dataset", required=True)
    r.add_argument("--provider", choices=("cpu", "cuda"), required=True)
    r.add_argument("--limit", type=int, default=50, help="0 means all")
    r.add_argument("--stages", default=",".join(STAGES))
    r.add_argument("--migan-limit", type=int, default=5)
    r.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    r.add_argument("--model-cache", default=None)
    r.add_argument("--output", required=True)
    c = sub.add_parser("compare")
    c.add_argument("baseline")
    c.add_argument("candidate")
    return p


def main():
    args = parser().parse_args()
    return compare(args) if args.command == "compare" else run(args)


if __name__ == "__main__":
    raise SystemExit(main())
