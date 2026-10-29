"""Bounded DirectML root-cause probe for the real Windows target.

This is deliberately not a benchmark. It isolates:
- ORT / DirectML availability;
- per-model session creation;
- the first session.run call;
- selected provider options;
- targeted retry variants for model-specific DML initialization failures.

Every model probe runs in a fresh subprocess so a native DirectML hang can be
terminated without wedging the GUI or preventing later probes.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import onnxruntime as ort


PROBE_KEYS = (
    "yunet",
    "ediffiqa",
    "3ddfa",
    "composite_person",
    "composite_head",
    "ocr",
    "isnetis",
    "migan",
)

MODEL_PATHS = {
    "yunet": "yunet_2023mar.onnx",
    "ediffiqa": "ediffiqa_t.onnx",
    "3ddfa": "mb1_120x120.onnx",
    "composite_person": "composite_split_cache/person_detect_v1.3_s/model.onnx",
    "composite_head": "composite_split_cache/head_detect_v2.0_s/model.onnx",
    "ocr": "ppocrv5_mobile_det/inference.onnx",
    "isnetis": "auto_crop/skytnt_anime_seg_isnetis/isnetis.onnx",
    "migan": "text_cleanup/migan/migan_pipeline_v2.onnx",
}

PREFERRED_SHAPES = {
    "yunet": (1, 3, 320, 320),
    "ediffiqa": (1, 3, 112, 112),
    "3ddfa": (1, 3, 120, 120),
    "composite_person": (1, 3, 640, 640),
    "composite_head": (1, 3, 640, 640),
    "ocr": (1, 3, 736, 736),
    "isnetis": (1, 3, 1024, 1024),
}

SESSION_TIMEOUT_SECONDS = 60
RUN_TIMEOUT_SECONDS = 60
BOOT_TIMEOUT_SECONDS = 20


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def models_root() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "models"
    return app_dir() / "resources" / "models"


def report_root() -> Path:
    root = app_dir() / "directml-diagnostic-results" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    return root


def append_event(path: Path, event: str, **payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "monotonic": time.monotonic(),
        "event": event,
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def ort_dtype(type_name: str):
    mapping = {
        "tensor(float)": np.float32,
        "tensor(float16)": np.float16,
        "tensor(double)": np.float64,
        "tensor(int64)": np.int64,
        "tensor(int32)": np.int32,
        "tensor(uint8)": np.uint8,
        "tensor(int8)": np.int8,
        "tensor(bool)": np.bool_,
    }
    dtype = mapping.get(str(type_name))
    if dtype is None:
        raise RuntimeError(f"Unsupported diagnostic input dtype: {type_name}")
    return dtype


def _shape_from_metadata(node, preferred):
    output = []
    shape = list(node.shape or [])
    for index, dim in enumerate(shape):
        if isinstance(dim, int) and dim > 0:
            output.append(dim)
        elif preferred and index < len(preferred):
            output.append(int(preferred[index]))
        else:
            output.append(1)
    return tuple(output)


def make_feeds(session, key: str):
    feeds = {}
    preferred = PREFERRED_SHAPES.get(key)

    for node in session.get_inputs():
        name = str(node.name)
        dtype = ort_dtype(node.type)

        if key == "migan":
            lower = name.casefold()
            channels = 1 if "mask" in lower else 3
            preferred_input = (1, channels, 256, 256)
            shape = _shape_from_metadata(node, preferred_input)
            if "mask" in lower:
                value = np.ones(shape, dtype=dtype)
            else:
                value = np.zeros(shape, dtype=dtype)
        else:
            shape = _shape_from_metadata(node, preferred)
            value = np.zeros(shape, dtype=dtype)

        feeds[name] = np.ascontiguousarray(value)

    if not feeds:
        raise RuntimeError("Model exposes no inputs.")
    return feeds


def session_options(variant: str):
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_mem_pattern = False
    options.log_severity_level = 2

    if variant == "graphopt_off":
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    else:
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return options


def dml_provider(variant: str, device_id):
    options = {}
    if device_id is not None:
        options["device_id"] = str(int(device_id))
    if variant == "metacommands_off":
        options["disable_metacommands"] = "true"
    return ("DmlExecutionProvider", options) if options else "DmlExecutionProvider"


def _ensure_src_path():
    if getattr(sys, "frozen", False):
        return
    src = app_dir() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def create_session(model, args):
    if args.route == "shared":
        if args.variant != "default" or args.device_id is not None:
            raise ValueError("shared route only supports default variant/automatic device selection")
        _ensure_src_path()
        from infrastructure import inference_runtime
        from infrastructure.runtime_tuning import configure_ort_cpu_options

        inference_runtime.configure_inference_runtime("gpu")
        return inference_runtime.create_ort_session(
            ort,
            str(model),
            sess_options=configure_ort_cpu_options(ort),
        )

    options = session_options(args.variant)
    providers = ["CPUExecutionProvider"]
    if args.provider == "directml":
        providers = [dml_provider(args.variant, args.device_id), "CPUExecutionProvider"]
    return ort.InferenceSession(
        str(model),
        sess_options=options,
        providers=providers,
    )


def child_probe(args) -> int:
    progress = Path(args.progress).resolve()
    result_path = Path(args.output).resolve()
    model = models_root() / MODEL_PATHS[args.model]

    result = {
        "schema_version": 1,
        "model": args.model,
        "model_path": str(model),
        "variant": args.variant,
        "device_id": args.device_id,
        "provider": args.provider,
        "route": args.route,
        "platform": platform.platform(),
        "python": sys.version,
        "onnxruntime_version": getattr(ort, "__version__", "unknown"),
        "onnxruntime_module": str(getattr(ort, "__file__", "")),
        "available_providers": list(ort.get_available_providers()),
        "status": "started",
    }

    append_event(progress, "child_started", **{k: result[k] for k in ("model", "variant", "device_id", "provider")})

    try:
        if not model.is_file():
            raise FileNotFoundError(model)

        provider_description = (
            "shared_runtime"
            if args.route == "shared"
            else [
                dml_provider(args.variant, args.device_id),
                "CPUExecutionProvider",
            ] if args.provider == "directml" else ["CPUExecutionProvider"]
        )

        append_event(
            progress,
            "session_create_started",
            route=args.route,
            providers=provider_description,
        )
        t0 = time.perf_counter()
        session = create_session(model, args)
        session_seconds = time.perf_counter() - t0
        provider_options = session.get_provider_options()
        append_event(
            progress,
            "session_create_finished",
            seconds=round(session_seconds, 6),
            providers=list(session.get_providers()),
            provider_options=provider_options,
        )

        result["session_create_seconds"] = round(session_seconds, 6)
        result["session_providers"] = list(session.get_providers())
        result["provider_options"] = provider_options
        result["inputs"] = [
            {"name": item.name, "shape": item.shape, "type": item.type}
            for item in session.get_inputs()
        ]

        feeds = make_feeds(session, args.model)
        result["feed_shapes"] = {name: list(value.shape) for name, value in feeds.items()}
        result["feed_dtypes"] = {name: str(value.dtype) for name, value in feeds.items()}

        append_event(progress, "first_run_started", feeds=result["feed_shapes"])
        t1 = time.perf_counter()
        outputs = session.run(None, feeds)
        run_seconds = time.perf_counter() - t1
        append_event(
            progress,
            "first_run_finished",
            seconds=round(run_seconds, 6),
            output_shapes=[list(np.asarray(value).shape) for value in outputs],
        )
        result["first_run_seconds"] = round(run_seconds, 6)
        result["output_shapes"] = [list(np.asarray(value).shape) for value in outputs]
        result["status"] = "pass"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        append_event(progress, "child_finished", status="pass")
        return 0
    except Exception as exc:
        result["status"] = "error"
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        append_event(progress, "child_finished", status="error", error=str(exc))
        return 2


def child_command(model, variant, device_id, output, progress, provider="directml", route="raw"):
    args = [
        "--probe-child",
        "--model",
        model,
        "--variant",
        variant,
        "--provider",
        provider,
        "--route",
        route,
        "--output",
        str(output),
        "--progress",
        str(progress),
    ]
    if device_id is not None:
        args.extend(["--device-id", str(device_id)])
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def read_events(path: Path):
    if not path.exists():
        return []
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        return rows
    return rows


def kill_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass
    try:
        process.kill()
    except Exception:
        pass


def run_bounded_probe(root: Path, model: str, variant: str = "default", device_id=None, provider="directml", route="raw"):
    suffix = f"{model}__{route}__{variant}__device-{device_id if device_id is not None else 'auto'}__{provider}"
    output = root / f"{suffix}.json"
    progress = root / f"{suffix}.progress.jsonl"
    log = root / f"{suffix}.log"
    command = child_command(model, variant, device_id, output, progress, provider, route)

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    with log.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            command,
            cwd=str(app_dir()),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )

        started = time.monotonic()
        last_event_count = 0
        phase = "boot"
        phase_started = started
        timeout = BOOT_TIMEOUT_SECONDS

        while process.poll() is None:
            events = read_events(progress)
            if len(events) != last_event_count:
                for event in events[last_event_count:]:
                    kind = event.get("event")
                    if kind == "session_create_started":
                        phase = "session_create"
                        phase_started = time.monotonic()
                        timeout = SESSION_TIMEOUT_SECONDS
                    elif kind == "session_create_finished":
                        phase = "post_session"
                        phase_started = time.monotonic()
                        timeout = BOOT_TIMEOUT_SECONDS
                    elif kind == "first_run_started":
                        phase = "first_run"
                        phase_started = time.monotonic()
                        timeout = RUN_TIMEOUT_SECONDS
                    elif kind in ("first_run_finished", "child_finished"):
                        phase = kind
                        phase_started = time.monotonic()
                        timeout = BOOT_TIMEOUT_SECONDS
                last_event_count = len(events)

            if time.monotonic() - phase_started > timeout:
                kill_tree(process)
                return {
                    "model": model,
                    "variant": variant,
                    "device_id": device_id,
                    "provider": provider,
                "route": route,
                    "route": route,
                    "status": "timeout",
                    "timeout_phase": phase,
                    "timeout_seconds": timeout,
                    "events": read_events(progress),
                    "log": str(log),
                }
            time.sleep(0.15)

        events = read_events(progress)
        if output.exists():
            try:
                result = json.loads(output.read_text(encoding="utf-8"))
            except Exception:
                result = {"status": "invalid_result"}
        else:
            result = {"status": "no_result"}
        result.update(
            {
                "model": model,
                "variant": variant,
                "device_id": device_id,
                "provider": provider,
                "exit_code": process.returncode,
                "events": events,
                "log": str(log),
            }
        )
        return result


def nvidia_info():
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,uuid,pci.bus_id,memory.total",
        "--format=csv,noheader",
    ]
    try:
        cp = subprocess.run(command, capture_output=True, text=True, timeout=8)
        return {
            "returncode": cp.returncode,
            "stdout": cp.stdout.strip(),
            "stderr": cp.stderr.strip(),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def windows_video_controllers():
    if os.name != "nt":
        return None
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,DriverVersion,AdapterRAM,PNPDeviceID | ConvertTo-Json -Compress",
    ]
    try:
        cp = subprocess.run(command, capture_output=True, text=True, timeout=10)
        return {
            "returncode": cp.returncode,
            "stdout": cp.stdout.strip(),
            "stderr": cp.stderr.strip(),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def failed(result):
    return result.get("status") != "pass"


def run_parent(gui_status=None):
    root = report_root()
    status = gui_status or (lambda _text: None)
    rows = []

    def run_one(model, variant="default", device_id=None, route="raw"):
        status(f"DirectML 诊断：{model} / {route} / {variant} / device={device_id if device_id is not None else 'auto'}")
        result = run_bounded_probe(root, model, variant, device_id, "directml", route)
        rows.append(result)
        return result

    # Smallest project ONNX first: prove whether raw ORT + DML can create and run
    # a compact graph before blaming the larger product models.
    sanity = run_one("yunet")

    # If even the small graph fails, try explicit adapter IDs as evidence. Invalid
    # IDs fail quickly; valid adapters are isolated by the subprocess watchdog.
    adapter_trials = []
    if failed(sanity):
        for device_id in (0, 1, 2):
            trial = run_one("yunet", "default", device_id)
            adapter_trials.append(trial)
            if not failed(trial):
                break

    shared_first_models = {"ediffiqa", "3ddfa"}

    for model in PROBE_KEYS[1:]:
        primary = run_one(model)
        if failed(primary):
            retry = run_one(model, "metacommands_off")
            if failed(retry):
                run_one(model, "graphopt_off")
        elif model in shared_first_models:
            # The integrated Ranking path uses the project's shared runtime,
            # not a raw ORT session. Probe both layers before moving on.
            run_one(model, route="shared")

    summary = {
        "schema_version": 1,
        "kind": "face-lora-directml-root-cause",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": sys.version,
        "onnxruntime_version": getattr(ort, "__version__", "unknown"),
        "available_providers": list(ort.get_available_providers()),
        "nvidia_smi": nvidia_info(),
        "windows_video_controllers": windows_video_controllers(),
        "models_root": str(models_root()),
        "probes": rows,
    }

    failures = [row for row in rows if row.get("status") != "pass"]
    summary["failure_count"] = len(failures)
    summary["timeouts"] = [
        {
            "model": row.get("model"),
            "variant": row.get("variant"),
            "device_id": row.get("device_id"),
            "phase": row.get("timeout_phase"),
        }
        for row in failures
        if row.get("status") == "timeout"
    ]
    report = root / "directml-root-cause.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, summary


def run_gui():
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

    app = QApplication.instance() or QApplication(sys.argv)

    QMessageBox.information(
        None,
        "Face LoRA DirectML 根因诊断",
        "这次不再跑 CPU 基线，也不读取你的数据集。\n\n"
        "程序只会逐个测试已经打包的 ONNX 模型，并把“创建 DirectML session”"
        "和“第一次推理”分开记录。每个模型都在独立子进程中，native 调用卡住会被自动终止，"
        "然后继续测试下一个模型。\n\n"
        "不会安装 Python / CUDA / Windows ML，也不会修改项目数据。",
    )

    progress = QProgressDialog("准备 DirectML 根因诊断…", None, 0, 0)
    progress.setWindowTitle("Face LoRA DirectML 根因诊断")
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.show()

    class Worker(QObject):
        status = Signal(str)
        finished = Signal(str, object)
        failed = Signal(str)

        @Slot()
        def run(self):
            try:
                path, summary = run_parent(self.status.emit)
                self.finished.emit(str(path), summary)
            except Exception:
                self.failed.emit(traceback.format_exc())

    thread = QThread()
    worker = Worker()
    worker.moveToThread(thread)

    def done(path, summary):
        progress.close()
        timeouts = summary.get("timeouts", [])
        lines = [
            f"探测完成：{len(summary.get('probes', []))} 项",
            f"失败/超时：{summary.get('failure_count', 0)}",
        ]
        if timeouts:
            first = timeouts[0]
            lines.append(
                f"首个超时：{first.get('model')} / {first.get('phase')} / {first.get('variant')}"
            )
        lines += ["", "请把这个文件发回给 ChatGPT：", path]
        QMessageBox.information(None, "DirectML 根因诊断完成", "\n".join(lines))
        thread.quit()

    def fail(details):
        progress.close()
        path = app_dir() / "directml-diagnostic-error.txt"
        path.write_text(details, encoding="utf-8")
        QMessageBox.critical(
            None,
            "DirectML 根因诊断失败",
            "诊断程序自身失败。请把这个文件发回给 ChatGPT：\n" + str(path),
        )
        thread.quit()

    worker.status.connect(progress.setLabelText)
    worker.finished.connect(done)
    worker.failed.connect(fail)
    thread.started.connect(worker.run)
    thread.finished.connect(app.quit)
    thread.start()
    app.exec()
    thread.wait()
    return 0


def parser():
    p = argparse.ArgumentParser(description="Bounded DirectML root-cause probe")
    p.add_argument("--probe-child", action="store_true")
    p.add_argument("--model", choices=PROBE_KEYS)
    p.add_argument("--variant", choices=("default", "metacommands_off", "graphopt_off"), default="default")
    p.add_argument("--device-id", type=int, default=None)
    p.add_argument("--provider", choices=("directml", "cpu"), default="directml")
    p.add_argument("--route", choices=("raw", "shared"), default="raw")
    p.add_argument("--output")
    p.add_argument("--progress")
    p.add_argument("--headless", action="store_true")
    return p


def main():
    args = parser().parse_args()
    if args.probe_child:
        if not args.model or not args.output or not args.progress:
            raise SystemExit("--probe-child requires --model, --output and --progress")
        return child_probe(args)
    if args.headless:
        path, _summary = run_parent(print)
        print(path)
        return 0
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
