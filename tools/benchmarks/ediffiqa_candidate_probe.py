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

# ORT may place helper kernels on CPU. The observed official model also puts
# one Gelu on CPU per inference. This must be disclosed rather than relabeled
# a shape helper, or mistaken for a CPU-only session fallback.
# Production acceptance keeps other CPU arithmetic as a separate blocker.
CPU_HELPER_OPS = frozenset({
    "Shape", "Size", "Gather", "GatherElements", "Slice", "Concat",
    "Unsqueeze", "Squeeze", "Reshape", "Flatten", "Expand", "Cast",
    "Identity", "Constant", "ConstantOfShape",
})
EXPECTED_CPU_COMPUTE_OPS = frozenset({"Gelu"})
GPU_COMPUTE_OPS = frozenset({
    "Conv", "FusedConv", "Gemm", "MatMul", "FusedMatMul",
    "DmlFusedNode", "DmlFused",
})


def summarize_execution_profile(events, expected_runs: int = 3):
    """Distinguish DML execution proof from the production mixed-EP gate.

    Counts are executed ORT profiler kernel events, NOT elapsed-time shares.
    Three deterministic inferences are required by the final target probe.
    The known eDifFIQA-T export has one CPU Gelu per inference; it is real
    CPU arithmetic and is never misrepresented as a mere shape helper.
    """
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
        op = str(args.get("op_name", "unknown"))
        if provider not in {"DmlExecutionProvider", "CPUExecutionProvider"}:
            continue
        executed += 1
        counts[provider] += 1
        operators.setdefault(provider, Counter())[op] += 1

    dml_ops = operators.get("DmlExecutionProvider", Counter())
    cpu_ops = operators.get("CPUExecutionProvider", Counter())
    cpu_non_helper = sorted(op for op in cpu_ops if op not in CPU_HELPER_OPS)
    unexpected_cpu_compute = sorted(
        op for op in cpu_non_helper if op not in EXPECTED_CPU_COMPUTE_OPS
    )
    dml_compute = sum(dml_ops.get(op, 0) for op in GPU_COMPUTE_OPS)
    cpu_gelu = cpu_ops.get("Gelu", 0)
    # This answers a factual question: did the DML EP execute arithmetic?
    # It deliberately does not claim whole-model GPU execution.
    gpu_compute_verified = dml_compute > 0
    # Separate, bounded acceptance for this SHA-pinned production export.
    # Only a single CPU Gelu per recorded inference is expected.
    production_execution_accepted = (
        gpu_compute_verified
        and dml_ops.get("Conv", 0) > 0
        and dml_ops.get("Gemm", 0) > 0
        and not unexpected_cpu_compute
        and cpu_gelu <= expected_runs
    )
    return {
        "source": "onnxruntime_kernel_profiling",
        "executed_kernel_events": executed,
        "provider_kernel_events": dict(sorted(counts.items())),
        "operators_by_provider": {
            key: dict(sorted(value.items())) for key, value in sorted(operators.items())
        },
        "dml_compute_kernel_events": dml_compute,
        "cpu_gelu_kernel_events": cpu_gelu,
        "cpu_non_helper_ops": cpu_non_helper,
        "unexpected_cpu_compute_ops": unexpected_cpu_compute,
        "gpu_compute_verified": gpu_compute_verified,
        "production_mixed_execution_accepted": production_execution_accepted,
        "cpu_nodes_executed": counts["CPUExecutionProvider"] > 0,
        "performance_verified": False,
        "note": (
            "DML core compute is separately evidenced by executed Conv/Gemm kernels. "
            "The official model may perform up to one CPU Gelu per inference. "
            "Kernel event counts are not wall-time, elapsed-time ratios, "
            "or proof of acceleration."
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
            append_event(progress, "profile_saved", profile_path=str(profile_path))
            events = json.loads(profile_path.read_text(encoding="utf-8"))
            summary = summarize_execution_profile(events, expected_runs=len(outputs))
            result["profile_summary"] = summary
            result["gpu_compute_verified"] = summary["gpu_compute_verified"]
            result["production_mixed_execution_accepted"] = summary["production_mixed_execution_accepted"]
            result["cpu_nodes_executed"] = summary["cpu_nodes_executed"]
            result["performance_verified"] = False
            if not summary["production_mixed_execution_accepted"]:
                raise RuntimeError(
                    "Core DML compute not proven, or unexpected CPU arithmetic assignment: "
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
        and row.get("production_mixed_execution_accepted") is True
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



BENCHMARK_WARMUP = 5
BENCHMARK_SAMPLES = 30
BENCHMARK_MAX_ABS_ERROR = 0.001


def run_performance_benchmark():
    """Bounded same-model CPU vs DML-mixed wall-time comparison on target.

    Uses a separately profiled DML preflight for placement evidence, then
    fresh unprofiled sessions for timing, so instrumentation does not bias
    the median. Measures blocking session.run wall-time, not UI throughput.
    """
    model = candidate_root() / PRODUCTION_CANDIDATE[1]
    destination = app_dir() / "qa-ediffiqa-performance.json"
    report = {
        "schema_version": 1,
        "kind": "ediffiqa-cpu-vs-directml-walltime",
        "status": "started",
        "model_sha256": None,
        "warmup_per_provider": BENCHMARK_WARMUP,
        "timed_samples_per_provider": BENCHMARK_SAMPLES,
        "max_allowed_abs_output_error": BENCHMARK_MAX_ABS_ERROR,
        "performance_verified": False,
        "target_gpu_verified": False,
        "error": None,
        "note": (
            "Synthetic eDifFIQA-T 112x112 tensor inference only; "
            "measures blocking session.run, excludes image pre/post-processing "
            "and UI. Separate CPU and DML sessions, alternating order, warm-up "
            "excluded. No inference timing includes ORT profiling overhead."
        ),
    }
    try:
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
        report["model_sha256"] = digest
        if digest != PRODUCTION_SHA256:
            raise ValueError("Production model SHA-256 mismatch: " + digest)

        # Profiling is restricted to a preflight session, never the timed one.
        profile_opts = session_options(True, str(app_dir() / "benchmark-dml-preflight"))
        preflight = ort.InferenceSession(
            str(model), sess_options=profile_opts,
            providers=["DmlExecutionProvider", "CPUExecutionProvider"],
            enable_fallback=False,
        )
        if "DmlExecutionProvider" not in preflight.get_providers():
            raise RuntimeError("DirectML provider missing during preflight.")
        profile_input = preflight.get_inputs()[0].name
        preflight.run(None, {profile_input: make_input(11)})
        profile_path = Path(preflight.end_profiling())
        placement = summarize_execution_profile(
            json.loads(profile_path.read_text(encoding="utf-8")),
            expected_runs=1,
        )
        report["preflight_profile"] = str(profile_path)
        report["preflight_profile_summary"] = placement
        report["target_gpu_verified"] = placement["gpu_compute_verified"]
        if not placement["production_mixed_execution_accepted"]:
            raise RuntimeError("DML preflight does not match the accepted mixed model placement.")

        sessions = {}
        for name, providers in (
            ("cpu", ["CPUExecutionProvider"]),
            ("directml", ["DmlExecutionProvider", "CPUExecutionProvider"]),
        ):
            started = time.perf_counter()
            sess = ort.InferenceSession(
                str(model), sess_options=session_options(False),
                providers=providers,
                enable_fallback=False,
            )
            seconds = time.perf_counter() - started
            got = list(sess.get_providers())
            if (name == "cpu" and "DmlExecutionProvider" in got) or (
                name == "directml" and "DmlExecutionProvider" not in got
            ):
                raise RuntimeError("Unexpected benchmark session provider assignment: " + repr(got))
            sessions[name] = sess
            report[name] = {
                "session_create_ms": round(seconds * 1000, 3),
                "session_providers": got,
                "samples_ms": [],
            }

        for i in range(BENCHMARK_WARMUP + BENCHMARK_SAMPLES):
            # Both providers receive the EXACT same tensor for every round.
            sample = make_input(1000 + i)
            order = ("cpu", "directml") if i % 2 == 0 else ("directml", "cpu")
            round_outputs = {}
            for name in order:
                sess = sessions[name]
                input_name = sess.get_inputs()[0].name
                started = time.perf_counter()
                value = np.asarray(sess.run(None, {input_name: sample})[0], dtype=np.float64)
                elapsed = (time.perf_counter() - started) * 1000
                if not np.all(np.isfinite(value)):
                    raise RuntimeError(name + " returned non-finite output.")
                round_outputs[name] = value
                if i >= BENCHMARK_WARMUP:
                    report[name]["samples_ms"].append(round(elapsed, 6))
            cpu_out = round_outputs["cpu"]
            dml_out = round_outputs["directml"]
            if cpu_out.shape != dml_out.shape:
                raise RuntimeError("CPU/DML output shape mismatch.")
            difference = float(np.max(np.abs(cpu_out - dml_out)))
            report["max_abs_output_difference"] = max(
                difference, report.get("max_abs_output_difference", 0.0)
            )
            if difference > BENCHMARK_MAX_ABS_ERROR:
                raise RuntimeError("CPU/DML output mismatch beyond tolerance: " + str(difference))

        for name in ("cpu", "directml"):
            ms = report[name]["samples_ms"]
            report[name]["median_ms"] = round(float(np.median(ms)), 6)
            report[name]["p90_ms"] = round(float(np.percentile(ms, 90)), 6)
            report[name]["mean_ms"] = round(float(np.mean(ms)), 6)
            if len(ms) != BENCHMARK_SAMPLES:
                raise RuntimeError("Timed sample count mismatch for " + name)
        dml_median = report["directml"]["median_ms"]
        if dml_median <= 0:
            raise RuntimeError("Invalid DirectML median.")
        report["cpu_to_directml_median_speedup"] = round(
            report["cpu"]["median_ms"] / dml_median, 4
        )
        report["performance_verified"] = True
        report["status"] = "benchmarked_mixed_directml"
    except Exception as exc:
        report["status"] = "benchmark_error"
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Single performance report:", destination)
    return 0 if report["status"] == "benchmarked_mixed_directml" else 2

def parser():
    p = argparse.ArgumentParser()
    p.add_argument("--child", action="store_true")
    p.add_argument("--candidate", choices=[x[0] for x in CANDIDATES])
    p.add_argument("--provider", choices=("cpu", "directml"), default="directml")
    p.add_argument("--output")
    p.add_argument("--progress")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--benchmark", action="store_true", help="Bounded CPU vs DirectML wall-time test.")
    return p


def main():
    args = parser().parse_args()
    if args.benchmark:
        return run_performance_benchmark()
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
