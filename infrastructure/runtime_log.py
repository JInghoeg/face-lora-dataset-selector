"""Process-wide runtime/fatal logging for the desktop application."""
from __future__ import annotations

import faulthandler
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback


_LOG_HANDLE = None
_LOG_PATH = None
_LOCK = threading.Lock()


def _root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "Face LoRA Dataset Selector" / "logs"


def setup_runtime_logging() -> Path:
    """Enable persistent Python + native fatal diagnostics for this process."""
    global _LOG_HANDLE, _LOG_PATH
    if _LOG_HANDLE is not None:
        return _LOG_PATH

    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = root / f"runtime-{stamp}-pid{os.getpid()}.log"
    handle = path.open("a", encoding="utf-8", buffering=1)
    _LOG_HANDLE = handle
    _LOG_PATH = path

    try:
        faulthandler.enable(file=handle, all_threads=True)
    except Exception:
        handle.write("faulthandler.enable failed:\n")
        handle.write(traceback.format_exc() + "\n")

    previous_excepthook = sys.excepthook

    def excepthook(exc_type, exc, tb):
        try:
            handle.write("\n=== unhandled exception ===\n")
            traceback.print_exception(exc_type, exc, tb, file=handle)
            handle.flush()
        finally:
            previous_excepthook(exc_type, exc, tb)

    sys.excepthook = excepthook

    if hasattr(threading, "excepthook"):
        previous_thread_hook = threading.excepthook

        def thread_hook(args):
            try:
                handle.write(
                    f"\n=== thread exception: {getattr(args.thread, 'name', '?')} ===\n"
                )
                traceback.print_exception(
                    args.exc_type,
                    args.exc_value,
                    args.exc_traceback,
                    file=handle,
                )
                handle.flush()
            finally:
                previous_thread_hook(args)

        threading.excepthook = thread_hook

    runtime_event("process_start", executable=sys.executable, frozen=bool(getattr(sys, "frozen", False)))
    return path


def runtime_event(name: str, **fields) -> None:
    handle = _LOG_HANDLE
    if handle is None:
        return
    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": str(name),
        **{key: str(value) for key, value in fields.items()},
    }
    try:
        with _LOCK:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
    except Exception:
        pass


def runtime_log_path() -> Path | None:
    return _LOG_PATH
