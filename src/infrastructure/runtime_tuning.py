"""Conservative native-runtime tuning so background analysis stays UI-friendly."""
from __future__ import annotations

import os


def analysis_thread_budget() -> int:
    explicit = os.environ.get("FACE_LORA_ANALYSIS_THREADS", "").strip()
    if explicit:
        try:
            return max(1, min(16, int(explicit)))
        except ValueError:
            pass
    cores = os.cpu_count() or 4
    # Model runtimes otherwise tend to consume every logical CPU from a
    # background QThread, which makes the Qt process itself feel frozen.
    return max(2, min(6, max(1, cores // 4)))


def configure_opencv_threads(cv2_module) -> int:
    budget = analysis_thread_budget()
    try:
        cv2_module.setNumThreads(budget)
    except Exception:
        pass
    return budget


def configure_ort_cpu_options(ort_module):
    options = ort_module.SessionOptions()
    options.graph_optimization_level = ort_module.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort_module.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = analysis_thread_budget()
    options.inter_op_num_threads = 1
    return options
