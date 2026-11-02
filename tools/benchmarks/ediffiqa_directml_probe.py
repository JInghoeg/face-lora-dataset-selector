"""Targeted eDifFIQA DirectML batch-1 probe.

This diagnostic exists to validate one specific hypothesis:
- the shipped eDifFIQA-T ONNX model exposes a symbolic batch dimension;
- production always calls it with exactly one aligned face;
- DirectML fails on first run for the dynamic-shape model;
- overriding symbolic dimension "batch" to 1 should preserve semantics while
  avoiding the dynamic Flatten/Reshape path.

No dataset is read and no benchmark is run.
"""
from __future__ import annotations

import argparse
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


TIMEOUT_SECONDS = 45


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def models_root() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        bundled = Path(sys._MEIPASS) / "models"
        if bundled.exists():
            return bundled
        sibling = Path(sys.executable).resolve().parent / "_internal" / "models"
        if sibling.exists():
            return sibling
    return app_dir() / "resources" / "models"


def model_path() -> Path:
    return models_root() / "ediffiqa_t.onnx"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def session_options(batch1: bool, strict_dml: bool = False):
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_mem_pattern = False
    if batch1:
        options.add_free_dimension_override_by_name("batch", 1)
    if strict_dml:
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        options.log_severity_level = 0
        options.log_verbosity_level = 1
    return options


def make_input(seed: int):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((1, 3, 112, 112), dtype=np.float32)


def child(args) -> int:
    out = Path(args.output).resolve()
    progress = Path(args.progress).resolve()
    model = model_path()

    def event(name, **payload):
        progress.parent.mkdir(parents=True, exist_ok=True)
        with progress.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event": name,
                        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        **payload,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            handle.flush()

    result = {
        "model_path": str(model),
        "model_sha256": sha256_file(model),
        "onnxruntime_version": ort.__version__,
        "available_providers": list(ort.get_available_providers()),
        "provider": args.provider,
        "batch1_override": bool(args.batch1),
        "strict_dml": bool(args.strict_dml),
        "status": "started",
    }

    try:
        providers = ["CPUExecutionProvider"]
        if args.provider == "directml":
            providers = (
                ["DmlExecutionProvider"]
                if args.strict_dml
                else ["DmlExecutionProvider", "CPUExecutionProvider"]
            )

        event(
            "session_create_started",
            provider=args.provider,
            batch1_override=bool(args.batch1),
            strict_dml=bool(args.strict_dml),
        )
        t0 = time.perf_counter()
        session = ort.InferenceSession(
            str(model),
            sess_options=session_options(args.batch1, args.strict_dml),
            providers=providers,
            enable_fallback=0 if args.strict_dml else 1,
        )
        result["session_create_seconds"] = round(time.perf_counter() - t0, 6)
        result["session_providers"] = list(session.get_providers())
        result["input_shape"] = list(session.get_inputs()[0].shape)
        if args.provider == "directml" and "DmlExecutionProvider" not in result["session_providers"]:
            raise RuntimeError(
                "DirectML was requested but the session fell back to "
                + repr(result["session_providers"])
            )
        event(
            "session_create_finished",
            seconds=result["session_create_seconds"],
            session_providers=result["session_providers"],
            input_shape=result["input_shape"],
        )

        outputs = []
        for seed in (11, 29, 47):
            data = make_input(seed)
            event("run_started", seed=seed)
            t1 = time.perf_counter()
            value = session.run(None, {"input": data})[0]
            elapsed = round(time.perf_counter() - t1, 6)
            arr = np.asarray(value)
            outputs.append(
                {
                    "seed": seed,
                    "seconds": elapsed,
                    "shape": list(arr.shape),
                    "value": arr.astype(np.float64).reshape(-1).tolist(),
                }
            )
            event("run_finished", seed=seed, seconds=elapsed, shape=list(arr.shape))

        result["outputs"] = outputs
        result["status"] = "pass"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        event("child_finished", status="pass")
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
        event("child_finished", status="error", error_type=type(exc).__name__, error=str(exc))
        return 2


def command(provider: str, batch1: bool, output: Path, progress: Path, strict_dml: bool = False):
    args = [
        "--child",
        "--provider",
        provider,
        "--output",
        str(output),
        "--progress",
        str(progress),
    ]
    if batch1:
        args.append("--batch1")
    if strict_dml:
        args.append("--strict-dml")
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def run_bounded(root: Path, provider: str, batch1: bool, strict_dml: bool = False):
    strict_suffix = "-strict" if strict_dml else ""
    label = f"{provider}-{'batch1' if batch1 else 'dynamic'}{strict_suffix}"
    output = root / f"{label}.json"
    progress = root / f"{label}.progress.jsonl"
    log = root / f"{label}.log"

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    with log.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            command(provider, batch1, output, progress, strict_dml),
            cwd=str(app_dir()),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        try:
            process.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
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
            return {
                "provider": provider,
                "batch1_override": batch1,
                "strict_dml": strict_dml,
                "status": "timeout",
                "timeout_seconds": TIMEOUT_SECONDS,
                "progress": progress.read_text(encoding="utf-8") if progress.exists() else "",
                "log": str(log),
            }

    if output.exists():
        result = json.loads(output.read_text(encoding="utf-8"))
    else:
        result = {"status": "no_result", "exit_code": process.returncode}
    result["log"] = str(log)
    result["exit_code"] = process.returncode
    return result


def compare_cpu(dynamic, fixed):
    if dynamic.get("status") != "pass" or fixed.get("status") != "pass":
        return {"comparable": False}

    rows = []
    all_close = True
    for left, right in zip(dynamic["outputs"], fixed["outputs"]):
        a = np.asarray(left["value"], dtype=np.float64)
        b = np.asarray(right["value"], dtype=np.float64)
        delta = float(np.max(np.abs(a - b))) if a.size else 0.0
        close = bool(np.allclose(a, b, rtol=1e-6, atol=1e-7))
        all_close = all_close and close
        rows.append({"seed": left["seed"], "max_abs_diff": delta, "allclose": close})
    return {"comparable": True, "allclose": all_close, "rows": rows}


def result_root() -> Path:
    root = app_dir() / "ediffiqa-directml-results" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_parent(status=lambda _text: None):
    root = result_root()

    status("CPU：验证 batch=1 override 输出等价…")
    cpu_dynamic = run_bounded(root, "cpu", False)
    cpu_batch1 = run_bounded(root, "cpu", True)
    equivalence = compare_cpu(cpu_dynamic, cpu_batch1)

    status("DirectML：复现动态 batch 路径…")
    dml_dynamic = run_bounded(root, "directml", False)

    status("DirectML：测试 batch=1 override（允许 fallback，用于复现）…")
    dml_batch1 = run_bounded(root, "directml", True)

    status("DirectML：严格测试 batch=1，不允许 CPU fallback…")
    dml_batch1_strict = run_bounded(root, "directml", True, strict_dml=True)

    report = {
        "schema_version": 1,
        "kind": "ediffiqa-directml-batch1",
        "model_path": str(model_path()),
        "model_sha256": sha256_file(model_path()),
        "cpu_dynamic": cpu_dynamic,
        "cpu_batch1": cpu_batch1,
        "cpu_equivalence": equivalence,
        "directml_dynamic": dml_dynamic,
        "directml_batch1": dml_batch1,
        "directml_batch1_strict": dml_batch1_strict,
        "batch1_keeps_directml": bool(
            dml_batch1.get("status") == "pass"
            and "DmlExecutionProvider" in dml_batch1.get("session_providers", [])
        ),
        "hypothesis_supported": bool(
            equivalence.get("allclose")
            and dml_batch1_strict.get("status") == "pass"
            and "DmlExecutionProvider" in dml_batch1_strict.get("session_providers", [])
            and dml_dynamic.get("status") != "pass"
        ),
    }
    path = root / "ediffiqa-directml-batch1.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, report


def run_gui():
    from PySide6.QtCore import QObject, QThread, Signal, Slot
    from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

    app = QApplication.instance() or QApplication(sys.argv)

    QMessageBox.information(
        None,
        "eDifFIQA DirectML 定向诊断",
        "这次只测试 eDifFIQA-T。\n\n"
        "先验证 CPU 下动态 batch 与 batch=1 override 输出等价，"
        "再分别测试两种 DirectML first-run。\n\n"
        "不读取数据集，不测试其他模型。",
    )

    progress = QProgressDialog("准备…", None, 0, 0)
    progress.setWindowTitle("eDifFIQA DirectML 定向诊断")
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

    thread = QThread()
    worker = Worker()
    worker.moveToThread(thread)

    class UiBridge(QObject):
        @Slot(str, object)
        def done(self, path, report):
            progress.close()
            fixed = report.get("directml_batch1_strict", {})
            equivalent = report.get("cpu_equivalence", {}).get("allclose")
            providers = fixed.get("session_providers", [])
            QMessageBox.information(
                None,
                "eDifFIQA 定向诊断完成",
                "CPU 输出等价：{}\n严格 DirectML batch=1：{}\nProvider：{}\n\n报告：\n{}".format(
                    "PASS" if equivalent else "FAIL",
                    str(fixed.get("status", "unknown")).upper(),
                    ", ".join(providers) if providers else "无",
                    path,
                ),
            )
            thread.quit()

        @Slot(str)
        def fail(self, details):
            progress.close()
            path = app_dir() / "ediffiqa-directml-probe-error.txt"
            path.write_text(details, encoding="utf-8")
            QMessageBox.critical(None, "诊断失败", "请把这个文件发回：\n" + str(path))
            thread.quit()

    bridge = UiBridge()

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
    p.add_argument("--provider", choices=("cpu", "directml"), default="cpu")
    p.add_argument("--batch1", action="store_true")
    p.add_argument("--strict-dml", action="store_true")
    p.add_argument("--output")
    p.add_argument("--progress")
    p.add_argument("--headless", action="store_true")
    return p


def main():
    args = parser().parse_args()
    if args.child:
        if not args.output or not args.progress:
            raise SystemExit("--child requires --output and --progress")
        return child(args)
    if args.headless:
        path, _report = run_parent(print)
        print(path)
        return 0
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
