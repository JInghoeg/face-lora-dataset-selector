"""Strict target-RTX DirectML probe of the exact production eDifFIQA-T model.

The official re-export is SHA-pinned and CPU-equivalent in CI. Legacy ONNX
alternatives remain research-only; the target package tests exactly this file.
Python provider-level retry is disabled. ORT may still place small shape/helper
nodes on CPU: every executed node is audited from ORT profiling, and a GPU PASS
requires actual DML convolution/matrix computation, not provider registration.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import onnxruntime as ort


PRODUCTION_CANDIDATE = ("upstream_current", "ediffiqa_t_upstream.onnx")
CANDIDATES = (PRODUCTION_CANDIDATE,)
PRODUCTION_SHA256 = "7a83be63e6583ec5800fa0762e219b65b4b9f1721c4d210bfe2f16c0478832bb"
TIMEOUT_SECONDS = 45

# CPU shape/helper kernels can be deliberately assigned by ORT. Their presence
# does not prove a whole-session CPU fallback, but they remain visible in the
# report. CPU placement of arithmetic-heavy model nodes is NOT accepted.
CPU_HELPER_OPS = frozenset({
    "Shape", "Size", "Gather", "GatherElements", "Slice", "Concat",
    "Unsqueeze", "Squeeze", "Reshape", "Flatten", "Expand", "Cast",
    "Identity", "Constant", "ConstantOfShape",
})
GPU_COMPUTE_OPS = frozenset({
    "Conv", "FusedConv", "Gemm", "MatMul", "FusedMatMul",
})


def summarize_execution_profile(events):
    """Use ORT's executed-kernel trace; never infer GPU work from get_providers."""
    counts = Counter()
    operators = {}
    executed = 0
    for event in events:
        if not isinstance(event, dict) or event.get("cat") != "Node":
            continue
        if not str(event.get("name", "")).endswith("_kernel_time"):
            continue
        args = event.get("args")
        if not isinstance(args, dict):
            continue
        provider = args.get("provider")
        op = args.get("op_name", "unknown")
        if provider not in {"DmlExecutionProvider", "CPUExecutionProvider"}:
            continue
        executed += 1
        counts[provider] += 1
        operators.setdefault(provider, Counter())[str(op)] += 1
    dml_ops = operators.get("DmlExecutionProvider", Counter())
    cpu_ops = operators.get("CPUExecutionProvider", Counter())
    unsupported_cpu = sorted(op for op in cpu_ops if op not in CPU_HELPER_OPS)
    dml_compute = sum(dml_ops.get(op, 0) for op in GPU_COMPUTE_OPS)
    verified = dml_compute > 0 and not unsupported_cpu
    return {
        "source": "onnxruntime_kernel_profiling",
        "executed_kernel_events": executed,
        "provider_kernel_events": dict(sorted(counts.items())),
        "operators_by_provider": {
            key: dict(sorted(value.items())) for key, value in sorted(operators.items())
        },
        "dml_compute_kernel_events": dml_compute,
        "cpu_non_helper_ops": unsupported_cpu,
        "gpu_compute_verified": verified,
        "note": (
            "CPU helper kernels are allowed and disclosed; core arithmetic "
            "must execute on DML. Profile event counts are not GPU time or "
            "a performance benchmark."
        ),
    }



def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def candidate_root() -> Path:
    roots = [
        app_dir() / "ediffiqa-candidates",
        app_dir() / "_internal" / "ediffiqa-candidates",
        app_dir() / "_research_output" / "ediffiqa-graph-lab",
    ]
    for root in roots:
        if (root / PRODUCTION_CANDIDATE[1]).is_file():
            return root
    raise FileNotFoundError("Official eDifFIQA-T model not found beside the probe.")


def make_input(seed: int):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((1, 3, 112, 112), dtype=np.float32)


def session_options(strict_dml: bool, profile_prefix: str | None = None):
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_mem_pattern = False
    if strict_dml:
        # Do NOT forbid all CPU nodes: ORT intentionally places small shape
        # helpers (e.g. Expand) on CPU even when DML handles core arithmetic.
        # We audit every executed kernel in the profiler instead.
        options.enable_profiling = True
        if profile_prefix is not None:
            options.profile_file_prefix = profile_prefix
        options.log_severity_level = 2
    return options


def append_event(path: Path, event: str, **payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            **payload,
        }, ensure_ascii=False) + "\n")
        handle.flush()


def child(args) -> int:
    root = candidate_root()
    model = root / dict(CANDIDATES)[args.candidate]
    out = Path(args.output).resolve()
    progress = Path(args.progress).resolve()

    strict = args.provider == "directml"
    providers = ["CPUExecutionProvider"]
    kwargs = {}
    if strict:
        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
        # Disable Python-level fallback/re-creation as a CPU-only session.
        kwargs["enable_fallback"] = False

    result = {
        "candidate": args.candidate,
        "model_path": str(model),
        "model_size": model.stat().st_size if model.exists() else None,
        "provider_requested": args.provider,
        "onnxruntime_version": ort.__version__,
        "available_providers": list(ort.get_available_providers()),
        "status": "started",
    }

    try:
        if not model.is_file():
            raise FileNotFoundError(model)
        actual_sha256 = hashlib.sha256(model.read_bytes()).hexdigest()
        result["model_sha256"] = actual_sha256
        if actual_sha256 != PRODUCTION_SHA256:
            raise ValueError("Official eDifFIQA-T model SHA-256 mismatch: " + actual_sha256)

        append_event(progress, "session_create_started", candidate=args.candidate, provider=args.provider)
        t0 = time.perf_counter()
        session = ort.InferenceSession(
            str(model),
            sess_options=session_options(strict, str(out.parent / (args.candidate + "-ort-profile"))),
            providers=providers,
            **kwargs,
        )
        result["session_create_seconds"] = round(time.perf_counter() - t0, 6)
        result["session_providers"] = list(session.get_providers())
        result["input_shape"] = list(session.get_inputs()[0].shape)
        append_event(
            progress,
            "session_create_finished",
            candidate=args.candidate,
            seconds=result["session_create_seconds"],
            providers=result["session_providers"],
            input_shape=result["input_shape"],
        )

        if strict and "DmlExecutionProvider" not in result["session_providers"]:
            raise RuntimeError("Strict DirectML session lost DmlExecutionProvider: " + repr(result["session_providers"]))

        input_name = session.get_inputs()[0].name
        outputs = []
        for seed in (11, 29, 47):
            data = make_input(seed)
            append_event(progress, "run_started", candidate=args.candidate, seed=seed)
            t1 = time.perf_counter()
            value = np.asarray(session.run(None, {input_name: data})[0], dtype=np.float64)
            elapsed = round(time.perf_counter() - t1, 6)
            outputs.append({
                "seed": seed,
                "seconds": elapsed,
                "shape": list(value.shape),
                "value": value.reshape(-1).tolist(),
            })
            append_event(progress, "run_finished", candidate=args.candidate, seed=seed, seconds=elapsed)

        result["outputs"] = outputs
        if strict:
            # Profiling is saved after real inference; do not accept DML merely
            # because get_providers() reports DmlExecutionProvider.
            profile_path = Path(session.end_profiling())
            result["execution_profile"] = str(profile_path)
            append_event(progress, "profile_saved", path=str(profile_path))
            events = json.loads(profile_path.read_text(encoding="utf-8"))
            summary = summarize_execution_profile(events)
            result["profile_summary"] = summary
            result["gpu_compute_verified"] = summary["gpu_compute_verified"]
            if not summary["gpu_compute_verified"]:
                raise RuntimeError(
                    "DML kernel proof missing or CPU non-helper kernels observed: "
                    + json.dumps(summary, ensure_ascii=False)
                )
        result["status"] = "pass"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        append_event(progress, "child_finished", candidate=args.candidate, status="pass")
        return 0
    except Exception as exc:
        result["status"] = "error"
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        append_event(
            progress,
            "child_finished",
            candidate=args.candidate,
            status="error",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 2


def command(candidate, provider, output, progress):
    args = [
        "--child",
        "--candidate", candidate,
        "--provider", provider,
        "--output", str(output),
        "--progress", str(progress),
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


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


def run_bounded(root: Path, candidate: str, provider="directml"):
    output = root / f"{candidate}-{provider}.json"
    progress = root / f"{candidate}-{provider}.progress.jsonl"
    log = root / f"{candidate}-{provider}.log"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    with log.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            command(candidate, provider, output, progress),
            cwd=str(app_dir()),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        try:
            process.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            kill_tree(process)
            return {
                "candidate": candidate,
                "provider_requested": provider,
                "status": "timeout",
                "timeout_seconds": TIMEOUT_SECONDS,
                "progress": progress.read_text(encoding="utf-8") if progress.exists() else "",
                "log": str(log),
            }

    result = (
        json.loads(output.read_text(encoding="utf-8"))
        if output.exists()
        else {"candidate": candidate, "status": "no_result"}
    )
    result["exit_code"] = process.returncode
    result["log"] = str(log)
    return result


def result_root() -> Path:
    root = app_dir() / "ediffiqa-candidate-results" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_parent(status=lambda _text: None):
    root = result_root()
    status("严格 DirectML：当前官方 eDifFIQA-T…")
    row = run_bounded(root, PRODUCTION_CANDIDATE[0], "directml")
    passed = (
        row.get("status") == "pass"
        and row.get("model_sha256") == PRODUCTION_SHA256
        and "DmlExecutionProvider" in row.get("session_providers", [])
        and row.get("gpu_compute_verified") is True
    )
    winner = PRODUCTION_CANDIDATE[0] if passed else None

    # Keep the existing report keys/file for compatible downstream collection.
    report = {
        "schema_version": 1,
        "kind": "ediffiqa-directml-candidates",
        "candidate_root": str(candidate_root()),
        "probes": [row],
        "winner": winner,
        "all_directml_passes": [winner] if winner else [],
    }
    path = root / "ediffiqa-directml-candidates.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, report


def run_gui():
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.information(
        None,
        "eDifFIQA DirectML 官方模型诊断",
        "这次只测试已经通过仓库侧等价验证的当前官方 eDifFIQA-T。\n\n"
        "Python 层 CPU-only 回退已禁用。CPU 形状辅助节点允许存在，但必须有真实 DirectML 计算核执行记录才能判定通过。",
    )

    progress = QProgressDialog("准备…", None, 0, 0)
    progress.setWindowTitle("eDifFIQA DirectML 官方模型诊断")
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
                path, report = run_parent(self.status.emit)
                self.finished.emit(str(path), report)
            except Exception:
                self.failed.emit(traceback.format_exc())

    class Bridge(QObject):
        @Slot(str, object)
        def done(self, path, report):
            progress.close()
            winner = report.get("winner")
            QMessageBox.information(
                None,
                "eDifFIQA 官方模型诊断完成",
                "当前官方 eDifFIQA-T DirectML：{}\n\n报告：\n{}".format(
                    "PASS" if winner == "upstream_current" else "FAIL",
                    path,
                ),
            )
            thread.quit()

        @Slot(str)
        def fail(self, details):
            progress.close()
            path = app_dir() / "ediffiqa-candidate-probe-error.txt"
            path.write_text(details, encoding="utf-8")
            QMessageBox.critical(None, "诊断失败", "请把这个文件发回：\n" + str(path))
            thread.quit()

    thread = QThread()
    worker = Worker()
    bridge = Bridge()
    worker.moveToThread(thread)
    worker.status.connect(progress.setLabelText)
    worker.finished.connect(bridge.done)
    worker.failed.connect(bridge.fail)
    thread.started.connect(worker.run)
    thread.finished.connect(app.quit)
    thread.start()
    app.exec()
    thread.wait()
    return 0


def parser():
    p = argparse.ArgumentParser()
    p.add_argument("--child", action="store_true")
    p.add_argument("--candidate", choices=[x[0] for x in CANDIDATES])
    p.add_argument("--provider", choices=("cpu", "directml"), default="directml")
    p.add_argument("--output")
    p.add_argument("--progress")
    p.add_argument("--headless", action="store_true")
    return p


def main():
    args = parser().parse_args()
    if args.child:
        if not args.candidate or not args.output or not args.progress:
            raise SystemExit("--child requires --candidate, --output and --progress")
        return child(args)
    if args.headless:
        path, report = run_parent(print)
        print(path)
        return 0 if report["winner"] == PRODUCTION_CANDIDATE[0] else 2
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
