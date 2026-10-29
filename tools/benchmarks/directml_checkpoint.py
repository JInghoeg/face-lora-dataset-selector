"""One-shot GUI wrapper for the final CPU-vs-DirectML target checkpoint.

The packaged checkpoint is self-contained. It never installs Python, Conda,
Windows ML, CUDA, or a system execution provider. All temporary evidence stays
inside the checkpoint folder so the whole folder can be deleted afterward.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
)

import gpu_runtime_benchmark as benchmark


DEFAULT_LIMIT = 30
DEFAULT_STAGES = ",".join(benchmark.STAGES)
DEFAULT_MIGAN_LIMIT = 3
CPU_STAGE_TIMEOUT_SECONDS = 15 * 60
DIRECTML_STAGE_TIMEOUT_SECONDS = 4 * 60
PROVIDER_STARTUP_TIMEOUT_SECONDS = 90
PROVIDER_TOTAL_TIMEOUT_SECONDS = 12 * 60

STAGE_LABELS = {
    "ranking": "Ranking",
    "auto_crop": "Auto Crop",
    "composite": "Composite Split",
    "text_scan": "Text Scan",
    "migan": "MI-GAN",
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_models_root() -> Path:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "models"
    return app_dir() / "resources" / "models"


def worker_command(
    provider: str,
    dataset: Path,
    output: Path,
    progress: Path,
    limit: int,
) -> list[str]:
    args = [
        "--worker",
        "--provider",
        provider,
        "--dataset",
        str(dataset),
        "--output",
        str(output),
        "--progress",
        str(progress),
        "--limit",
        str(limit),
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def run_worker(args: argparse.Namespace) -> int:
    ns = SimpleNamespace(
        repo_root=str(app_dir()),
        dataset=str(Path(args.dataset).resolve()),
        provider=args.provider,
        limit=int(args.limit),
        stages=DEFAULT_STAGES,
        migan_limit=DEFAULT_MIGAN_LIMIT,
        model_cache=str(resource_models_root()),
        output=str(Path(args.output).resolve()),
        progress=str(Path(args.progress).resolve()) if args.progress else None,
    )
    return int(benchmark.run(ns))


def stage_map(report: dict) -> dict[str, dict]:
    return {
        str(row.get("stage")): row
        for row in report.get("stages", [])
        if row.get("stage")
    }


def session_rows(report: dict) -> list[dict]:
    result = []
    for stage in report.get("stages", []):
        for session in stage.get("onnx_sessions", []) or []:
            result.append(
                {
                    "stage": stage.get("stage"),
                    **session,
                }
            )
    return result


def compare_reports(cpu: dict, directml: dict) -> dict:
    cpu_stages = stage_map(cpu)
    dml_stages = stage_map(directml)
    rows = []

    for name in benchmark.STAGES:
        if name not in cpu_stages or name not in dml_stages:
            continue
        baseline = cpu_stages[name]
        candidate = dml_stages[name]
        cpu_wall = float(baseline.get("wall_seconds") or 0.0)
        dml_wall = float(candidate.get("wall_seconds") or 0.0)
        speedup = cpu_wall / dml_wall if dml_wall > 0 else None
        left_sig = baseline.get("signature_sha256")
        right_sig = candidate.get("signature_sha256")
        parity = (
            left_sig == right_sig
            if left_sig and right_sig
            else None
        )
        rows.append(
            {
                "stage": name,
                "cpu_wall_seconds": cpu_wall,
                "directml_wall_seconds": dml_wall,
                "speedup_x": round(speedup, 4) if speedup is not None else None,
                "output_parity": parity,
                "cpu_status": baseline.get("status"),
                "directml_status": candidate.get("status"),
            }
        )

    cpu_total = sum(
        float(row.get("wall_seconds") or 0.0)
        for row in cpu.get("stages", [])
        if row.get("status") == "ok"
    )
    dml_total = sum(
        float(row.get("wall_seconds") or 0.0)
        for row in directml.get("stages", [])
        if row.get("status") == "ok"
    )

    dml_sessions = session_rows(directml)
    cpu_sessions = session_rows(cpu)
    dml_active = any(
        (row.get("actual") or [None])[0] == "DmlExecutionProvider"
        for row in dml_sessions
    )
    unexpected_dml_fallbacks = [
        row
        for row in dml_sessions
        if (row.get("actual") or [None])[0] != "DmlExecutionProvider"
    ]

    parity_values = [
        row["output_parity"]
        for row in rows
        if row["output_parity"] is not None
    ]
    all_parity = bool(parity_values) and all(parity_values)
    all_ok = all(
        row["cpu_status"] == "ok" and row["directml_status"] == "ok"
        for row in rows
    )

    if not dml_active:
        status = "directml_not_active"
    elif not all_ok:
        status = "stage_error"
    elif not all_parity:
        status = "output_mismatch"
    else:
        status = "pass"

    return {
        "schema_version": 1,
        "kind": "face-lora-directml-target-checkpoint",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status,
        "dataset": directml.get("inputs", {}).get("dataset"),
        "images_selected": directml.get("inputs", {}).get("images_selected"),
        "cpu_total_wall_seconds": round(cpu_total, 6),
        "directml_total_wall_seconds": round(dml_total, 6),
        "overall_speedup_x": (
            round(cpu_total / dml_total, 4)
            if dml_total > 0
            else None
        ),
        "directml_active": dml_active,
        "output_parity_all_comparable_stages": all_parity,
        "stage_comparison": rows,
        "cpu_sessions": cpu_sessions,
        "directml_sessions": dml_sessions,
        "unexpected_directml_fallbacks": unexpected_dml_fallbacks,
        "cpu_gpu_telemetry": {
            row.get("stage"): row.get("gpu")
            for row in cpu.get("stages", [])
        },
        "directml_gpu_telemetry": {
            row.get("stage"): row.get("gpu")
            for row in directml.get("stages", [])
        },
        "notes": [
            "No source image pixels are modified by this checkpoint.",
            "CPU and DirectML run in separate processes using the same packaged models and selected image subset.",
            "The result is a performance/activation checkpoint, not a release approval.",
        ],
    }


def selected_images(dataset: Path, limit: int) -> list[Path]:
    try:
        from infrastructure.filesystem import IMAGE_EXTENSIONS
        extensions = set(IMAGE_EXTENSIONS)
    except Exception:
        extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

    files = sorted(
        [
            path
            for path in dataset.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        ],
        key=lambda value: str(value).casefold(),
    )
    if limit > 0 and len(files) > limit:
        if limit == 1:
            return [files[len(files) // 2]]
        indexes = [
            round(i * (len(files) - 1) / (limit - 1))
            for i in range(limit)
        ]
        return [files[i] for i in indexes]
    return files


def prime_file_cache(dataset: Path, limit: int) -> None:
    paths = selected_images(dataset, limit)
    model_root = resource_models_root()
    if model_root.exists():
        paths.extend(
            path for path in model_root.rglob("*") if path.is_file()
        )

    for path in paths:
        try:
            with path.open("rb") as handle:
                while handle.read(4 * 1024 * 1024):
                    pass
        except OSError:
            continue


class CheckpointWorker(QObject):
    status = Signal(str)
    finished = Signal(str, str)
    failed = Signal(str)

    def __init__(self, dataset: Path, output_dir: Path, limit: int = DEFAULT_LIMIT):
        super().__init__()
        self.dataset = Path(dataset)
        self.output_dir = Path(output_dir)
        self.limit = int(limit)

    def _run_provider(self, provider: str, output: Path, log) -> None:
        provider_label = "CPU" if provider == "cpu" else "DirectML GPU"
        self.status.emit(f"正在启动 {provider_label} 测试…")
        progress_path = output.with_suffix(".progress.jsonl")
        if progress_path.exists():
            progress_path.unlink()
        command = worker_command(
            provider,
            self.dataset,
            output,
            progress_path,
            self.limit,
        )
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        log.write(f"\n===== {provider.upper()} =====\n")
        log.write("COMMAND: " + " ".join(command) + "\n")
        log.flush()

        process = subprocess.Popen(
            command,
            cwd=str(app_dir()),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        provider_started = time.monotonic()
        current_stage = None
        stage_started = None
        seen_events = 0
        first_stage_seen = False
        last_status_second = -1

        def terminate(reason: str) -> None:
            log.write(f"\nTIMEOUT: {reason}\n")
            log.flush()
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            raise RuntimeError(reason)

        while True:
            now = time.monotonic()
            events = []
            if progress_path.exists():
                try:
                    lines = progress_path.read_text(encoding="utf-8").splitlines()
                    for raw in lines[seen_events:]:
                        try:
                            events.append(json.loads(raw))
                        except json.JSONDecodeError:
                            continue
                    seen_events = len(lines)
                except OSError:
                    pass

            for event in events:
                kind = event.get("event")
                if kind == "provider_setup_started":
                    self.status.emit(f"{provider_label}：初始化执行提供程序…")
                    log.write("PROVIDER SETUP START\n")
                    log.flush()
                elif kind == "provider_setup_finished":
                    self.status.emit(f"{provider_label}：执行提供程序初始化完成")
                    log.write(
                        "PROVIDER SETUP END: "
                        f"expected={event.get('expected_execution_provider')} "
                        f"available={event.get('available_providers')}\n"
                    )
                    log.flush()
                elif kind == "stage_started":
                    first_stage_seen = True
                    current_stage = str(event.get("stage") or "unknown")
                    stage_started = now
                    last_status_second = -1
                    label = STAGE_LABELS.get(current_stage, current_stage)
                    self.status.emit(f"{provider_label}：{label}…")
                    log.write(f"STAGE START: {current_stage}\n")
                    log.flush()
                elif kind == "stage_finished":
                    stage = str(event.get("stage") or current_stage or "unknown")
                    log.write(
                        f"STAGE END: {stage} status={event.get('status')} "
                        f"wall={event.get('wall_seconds')}\n"
                    )
                    log.flush()
                    if stage == current_stage:
                        current_stage = None
                        stage_started = None

            returncode = process.poll()
            if returncode is not None:
                break

            provider_elapsed = now - provider_started
            if provider_elapsed > PROVIDER_TOTAL_TIMEOUT_SECONDS:
                terminate(
                    f"{provider_label} 整体运行超过 "
                    f"{PROVIDER_TOTAL_TIMEOUT_SECONDS // 60} 分钟，已自动终止。"
                )

            if current_stage is None:
                if (not first_stage_seen) and provider_elapsed > PROVIDER_STARTUP_TIMEOUT_SECONDS:
                    terminate(
                        f"{provider_label} 在 {PROVIDER_STARTUP_TIMEOUT_SECONDS} 秒内"
                        "没有完成初始化并进入任何测试阶段，已自动终止。"
                    )
            elif stage_started is not None:
                stage_elapsed = now - stage_started
                timeout = (
                    CPU_STAGE_TIMEOUT_SECONDS
                    if provider == "cpu"
                    else DIRECTML_STAGE_TIMEOUT_SECONDS
                )
                second = int(stage_elapsed)
                if second != last_status_second:
                    last_status_second = second
                    label = STAGE_LABELS.get(current_stage, current_stage)
                    self.status.emit(
                        f"{provider_label}：{label}（{second}s）"
                    )
                if stage_elapsed > timeout:
                    label = STAGE_LABELS.get(current_stage, current_stage)
                    terminate(
                        f"{provider_label} 的 {label} 阶段超过 "
                        f"{timeout // 60} 分钟无结果，已自动终止。"
                    )

            time.sleep(0.25)

        if process.returncode != 0:
            raise RuntimeError(
                f"{provider} benchmark failed with exit code {process.returncode}"
            )
        if not output.exists():
            raise RuntimeError(f"{provider} benchmark exited without report: {output}")

    @Slot()
    def run(self) -> None:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            cpu_path = self.output_dir / "cpu.json"
            dml_path = self.output_dir / "directml.json"
            comparison_path = self.output_dir / "directml-comparison.json"
            log_path = self.output_dir / "checkpoint.log"

            self.status.emit("正在预热文件缓存…")
            prime_file_cache(self.dataset, self.limit)

            with log_path.open("w", encoding="utf-8") as log:
                self._run_provider("cpu", cpu_path, log)
                self._run_provider("directml", dml_path, log)

            cpu = json.loads(cpu_path.read_text(encoding="utf-8"))
            directml = json.loads(dml_path.read_text(encoding="utf-8"))
            comparison = compare_reports(cpu, directml)
            comparison_path.write_text(
                json.dumps(
                    comparison,
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            summary = (
                f"状态：{comparison['status']}\n"
                f"样本：{comparison.get('images_selected')} 张\n"
                f"CPU：{comparison['cpu_total_wall_seconds']:.2f}s\n"
                f"DirectML：{comparison['directml_total_wall_seconds']:.2f}s\n"
                f"总加速：{comparison.get('overall_speedup_x')}x\n"
                f"DirectML 实际启用：{comparison['directml_active']}"
            )
            self.finished.emit(str(comparison_path), summary)
        except Exception:
            self.failed.emit(traceback.format_exc())


def run_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.information(
        None,
        "Face LoRA GPU 性能验证",
        "这是一次只读性能验证。\n\n"
        "程序会从你选择的数据集中均匀抽取最多 30 张图片，"
        "依次运行 CPU 与 DirectML；不会修改源图片，也不会安装 "
        "Python、Conda、CUDA 或系统组件。\n\n"
        "测试结果只写入本程序目录下的 checkpoint-results 文件夹。",
    )
    folder = QFileDialog.getExistingDirectory(
        None,
        "选择用于性能验证的数据集文件夹",
        str(Path.home()),
    )
    if not folder:
        return 0

    dataset = Path(folder)
    count = len(selected_images(dataset, DEFAULT_LIMIT))
    if count == 0:
        QMessageBox.warning(
            None,
            "没有可测试图片",
            "所选文件夹中没有找到受支持的图片。",
        )
        return 2

    stamp = time.strftime("%Y%m%d-%H%M%S")
    output_dir = app_dir() / "checkpoint-results" / stamp

    progress = QProgressDialog(
        "准备性能验证…",
        None,
        0,
        0,
    )
    progress.setWindowTitle("Face LoRA GPU 性能验证")
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.show()

    thread = QThread()
    worker = CheckpointWorker(dataset, output_dir)
    worker.moveToThread(thread)

    result = {"code": 0}

    def on_status(text: str) -> None:
        progress.setLabelText(text)

    def on_finished(path: str, summary: str) -> None:
        result["code"] = 0
        progress.close()
        QMessageBox.information(
            None,
            "性能验证完成",
            summary
            + "\n\n请把这个文件发回给 ChatGPT：\n"
            + path
            + "\n\n上传后可以直接删除整个测试程序文件夹。",
        )
        thread.quit()

    def on_failed(details: str) -> None:
        result["code"] = 3
        progress.close()
        error_path = output_dir / "checkpoint-error.txt"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text(details, encoding="utf-8")
        QMessageBox.critical(
            None,
            "性能验证失败",
            "验证没有完成。错误已保存到：\n"
            + str(error_path)
            + "\n\n请把这个文件发回给 ChatGPT。",
        )
        thread.quit()

    worker.status.connect(on_status)
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    thread.started.connect(worker.run)
    thread.finished.connect(app.quit)
    thread.start()
    app.exec()
    thread.wait()
    return int(result["code"])


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Self-contained Face LoRA CPU-vs-DirectML checkpoint"
    )
    p.add_argument("--worker", action="store_true")
    p.add_argument(
        "--provider",
        choices=("cpu", "directml"),
    )
    p.add_argument("--dataset")
    p.add_argument("--output")
    p.add_argument("--progress")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return p


def main() -> int:
    args = parser().parse_args()
    if args.worker:
        if not args.provider or not args.dataset or not args.output:
            raise SystemExit(
                "--worker requires --provider, --dataset and --output"
            )
        return run_worker(args)
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
