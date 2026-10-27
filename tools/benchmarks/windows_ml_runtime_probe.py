#!/usr/bin/env python
"""Research-only Windows ML NVIDIA execution-provider probe.

This tool intentionally does not change product runtime requirements or feature
code. It evaluates whether Windows ML can dynamically acquire/register the
NVIDIA NvTensorRtRtx execution provider without bundling CUDA/cuDNN into the
application.

Use --ensure only when downloading/installing the compatible EP is acceptable.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import traceback
from importlib import metadata
from pathlib import Path
from typing import Any

TARGET_EP = "NvTensorRtRtxExecutionProvider"
MIN_WINDOWS_BUILD = 26100


def _enum_name(value: Any) -> str:
    return getattr(value, "name", None) or str(value)


def _dist_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _windows_build() -> int | None:
    if os.name != "nt":
        return None
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        return None


def _winrt_runtime_dll() -> Path | None:
    try:
        dist = metadata.distribution("winrt-runtime")
    except metadata.PackageNotFoundError:
        return None
    root = Path(str(dist.locate_file("")))
    return root / "winrt" / "msvcp140.dll"


def _disable_conflicting_winrt_dll() -> tuple[dict[str, Any], tuple[Path, Path] | None]:
    dll = _winrt_runtime_dll()
    result = {"path": str(dll) if dll else None, "changed": False}
    if dll is None or not dll.exists():
        return result, None
    disabled = dll.with_suffix(dll.suffix + ".disabled-by-face-lora-probe")
    if disabled.exists():
        result["disabled_path"] = str(disabled)
        result["note"] = "A prior disabled copy already exists; this run made no change."
        return result, None
    dll.replace(disabled)
    result["changed"] = True
    result["disabled_path"] = str(disabled)
    return result, (dll, disabled)


def _restore_conflicting_winrt_dll(change: tuple[Path, Path] | None) -> dict[str, Any]:
    if change is None:
        return {"attempted": False, "restored": False}
    original, disabled = change
    result = {
        "attempted": True,
        "original_path": str(original),
        "disabled_path": str(disabled),
        "restored": False,
    }
    try:
        if disabled.exists() and not original.exists():
            disabled.replace(original)
            result["restored"] = True
        elif original.exists():
            result["restored"] = True
            result["note"] = "Original DLL path already exists."
        else:
            result["note"] = "Disabled DLL was no longer present at restore time."
    except OSError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _ep_name_matches(left: Any, right: Any) -> bool:
    return str(left or "").casefold() == str(right or "").casefold()


def _provider_row(provider: Any) -> dict[str, Any]:
    row = {
        "name": str(getattr(provider, "name", "")),
        "ready_state": _enum_name(getattr(provider, "ready_state", None)),
    }
    package_id = getattr(provider, "package_id", None)
    if package_id is not None:
        row["package_name"] = str(getattr(package_id, "name", "") or "")
        version = getattr(package_id, "version", None)
        if version is not None:
            row["package_version"] = str(version)
    library_path = getattr(provider, "library_path", None)
    if library_path:
        row["library_path"] = str(library_path)
    return row


def _ep_device_row(device: Any) -> dict[str, Any]:
    hardware = getattr(device, "hardware_device", None) or getattr(device, "device", None)
    return {
        "ep_name": str(getattr(device, "ep_name", "") or ""),
        "hardware_type": _enum_name(getattr(hardware, "type", None)) if hardware else "",
    }


def _write_report(report: dict[str, Any], output: str | None) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(payload)
    if output:
        path = Path(output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote: {path}")


def run(args: argparse.Namespace) -> int:
    build = _windows_build()
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "face-lora-windows-ml-runtime-probe",
        "target_provider": TARGET_EP,
        "environment": {
            "platform": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "windows_build": build,
            "packages": {
                "onnxruntime-windowsml": _dist_version("onnxruntime-windowsml"),
                "onnxruntime": _dist_version("onnxruntime"),
                "winrt-runtime": _dist_version("winrt-runtime"),
                "wasdk-Microsoft.Windows.AI.MachineLearning": _dist_version(
                    "wasdk-Microsoft.Windows.AI.MachineLearning"
                ),
                "wasdk-Microsoft.Windows.ApplicationModel.DynamicDependency.Bootstrap": _dist_version(
                    "wasdk-Microsoft.Windows.ApplicationModel.DynamicDependency.Bootstrap"
                ),
            },
        },
        "requested": {
            "ensure": bool(args.ensure),
            "model": str(Path(args.model).resolve()) if args.model else None,
            "fix_winrt_runtime": bool(args.fix_winrt_runtime),
        },
        "status": "starting",
    }

    if os.name != "nt":
        report["status"] = "unsupported_os"
        report["error"] = "Windows ML probe requires Windows."
        _write_report(report, args.output)
        return 2

    if build is not None and build < MIN_WINDOWS_BUILD:
        report["status"] = "unsupported_windows_build"
        report["error"] = (
            f"Windows build {build} is below {MIN_WINDOWS_BUILD}; "
            "catalog-delivered hardware EPs require Windows 11 24H2 or newer."
        )
        _write_report(report, args.output)
        return 2

    dll = _winrt_runtime_dll()
    report["winrt_runtime_dll"] = {
        "path": str(dll) if dll else None,
        "exists": bool(dll and dll.exists()),
    }
    winrt_dll_change = None
    if args.fix_winrt_runtime:
        workaround, winrt_dll_change = _disable_conflicting_winrt_dll()
        report["winrt_runtime_dll_workaround"] = workaround

    try:
        try:
            from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import (
                InitializeOptions,
                initialize,
            )
            import winui3.microsoft.windows.ai.machinelearning as winml
            import onnxruntime as ort
        except Exception as exc:
            report["status"] = "dependency_import_failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
            report["traceback"] = traceback.format_exc()
            return 3

        report["environment"]["onnxruntime_version"] = getattr(
            ort, "__version__", "unknown"
        )
        report["environment"]["static_providers"] = list(
            ort.get_available_providers()
        )
        get_ep_devices = getattr(ort, "get_ep_devices", None)
        if not callable(get_ep_devices):
            report["status"] = "unsupported_onnxruntime_api"
            report["error"] = (
                "onnxruntime-windowsml does not expose get_ep_devices()."
            )
            return 3
        report["environment"]["ep_devices_before_registration"] = [
            _ep_device_row(d) for d in get_ep_devices()
        ]

        try:
            # Keep research discovery non-interactive. ON_NO_MATCH_SHOW_UI can
            # display a system dialog when the matching Windows App SDK Runtime
            # is missing; CI/discovery must report that state instead.
            try:
                bootstrap = initialize(options=InitializeOptions.NONE)
            except OSError as exc:
                report["status"] = "app_sdk_runtime_unavailable"
                report["error"] = f"{type(exc).__name__}: {exc}"
                report["traceback"] = traceback.format_exc()
                return 9

            with bootstrap:
                catalog = winml.ExecutionProviderCatalog.get_default()
                providers = list(catalog.find_all_providers())
                report["catalog"] = [_provider_row(p) for p in providers]

                target = next(
                    (
                        p
                        for p in providers
                        if _ep_name_matches(getattr(p, "name", ""), TARGET_EP)
                    ),
                    None,
                )
                if target is None:
                    report["status"] = "target_provider_unavailable"
                    report["error"] = (
                        f"{TARGET_EP} is not advertised for this "
                        "device/driver combination."
                    )
                    return 4

                actual_target_name = str(getattr(target, "name", "") or TARGET_EP)
                report["catalog_target_name"] = actual_target_name
                ready_state = getattr(target, "ready_state", None)
                report["target_before"] = _provider_row(target)

                not_present = getattr(
                    winml.ExecutionProviderReadyState, "NOT_PRESENT", None
                )
                not_ready = getattr(
                    winml.ExecutionProviderReadyState, "NOT_READY", None
                )
                ready = getattr(
                    winml.ExecutionProviderReadyState, "READY", None
                )

                if ready_state == not_present and not args.ensure:
                    report["status"] = "download_required"
                    report["error"] = (
                        "Target EP is not installed. Re-run with --ensure only "
                        "after explicitly accepting the system-managed EP download."
                    )
                    return 5

                if ready_state in (not_present, not_ready):
                    result = target.ensure_ready_async().get()
                    report["ensure_result"] = {
                        "status": _enum_name(getattr(result, "status", None)),
                        "diagnostic_text": str(
                            getattr(result, "diagnostic_text", "") or ""
                        ),
                        "extended_error": str(
                            getattr(result, "extended_error", "") or ""
                        ),
                    }

                report["target_after"] = _provider_row(target)
                if getattr(target, "ready_state", None) != ready:
                    report["status"] = "target_not_ready"
                    report["error"] = (
                        f"{TARGET_EP} did not reach READY after preparation."
                    )
                    return 6

                library_path = str(
                    getattr(target, "library_path", "") or ""
                )
                if not library_path:
                    report["status"] = "missing_provider_library"
                    report["error"] = (
                        "Windows ML returned no provider library path."
                    )
                    return 7

                # Native catalog registration does not populate Python ORT.
                # Register the library directly into the Python ORT environment.
                ort.register_execution_provider_library(
                    actual_target_name, library_path
                )
                ep_devices = list(get_ep_devices())
                report["environment"]["ep_devices_after_registration"] = [
                    _ep_device_row(d) for d in ep_devices
                ]
                target_devices = [
                    d
                    for d in ep_devices
                    if _ep_name_matches(
                        getattr(d, "ep_name", ""), actual_target_name
                    )
                ]
                if not target_devices:
                    report["status"] = "registration_not_visible"
                    report["error"] = (
                        f"{TARGET_EP} registered without exposing an OrtEpDevice."
                    )
                    return 7

                if args.model:
                    model = Path(args.model).resolve()
                    if not model.is_file():
                        raise FileNotFoundError(model)

                    # Dynamically registered Windows ML EPs use OrtEpDevice +
                    # SessionOptions rather than the legacy static providers=
                    # list used by built-in CUDAExecutionProvider.
                    options = ort.SessionOptions()
                    options.add_provider_for_devices(
                        [target_devices[0]], {}
                    )
                    if not options.has_providers():
                        raise RuntimeError(
                            "NVIDIA OrtEpDevice was not attached to "
                            "SessionOptions."
                        )
                    session = ort.InferenceSession(
                        str(model), sess_options=options
                    )
                    report["session"] = {
                        "model": str(model),
                        "providers": list(session.get_providers()),
                        "selected_ep_device": _ep_device_row(
                            target_devices[0]
                        ),
                        "inputs": [
                            {
                                "name": item.name,
                                "shape": item.shape,
                                "type": item.type,
                            }
                            for item in session.get_inputs()
                        ],
                    }
                    if args.check_cpu_fallback:
                        cpu = ort.InferenceSession(
                            str(model),
                            providers=["CPUExecutionProvider"],
                        )
                        report["cpu_fallback_session"] = {
                            "providers": list(cpu.get_providers())
                        }

                report["status"] = "pass"
                return 0

        except Exception as exc:
            report["status"] = "probe_failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
            report["traceback"] = traceback.format_exc()
            return 8
    finally:
        # Any temporary pywinrt DLL rename is restored only after the Windows
        # ML/bootstrap context has unwound, avoiding a restore attempt while
        # the runtime may still hold the file loaded.
        if args.fix_winrt_runtime:
            report["winrt_runtime_dll_restore"] = (
                _restore_conflicting_winrt_dll(winrt_dll_change)
            )
        _write_report(report, args.output)

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Research-only Windows ML NVIDIA EP registration/session probe"
    )
    p.add_argument(
        "--ensure",
        action="store_true",
        help="Allow Windows ML to download/install the target EP if missing.",
    )
    p.add_argument(
        "--model",
        help="Optional ONNX model used to validate session creation after registration.",
    )
    p.add_argument(
        "--check-cpu-fallback",
        action="store_true",
        help="Also create a CPU-only session for the same model.",
    )
    p.add_argument(
        "--fix-winrt-runtime",
        action="store_true",
        help=(
            "Reversibly rename winrt/msvcp140.dll to avoid the pywinrt conflict "
            "called out by Microsoft. Research environment only."
        ),
    )
    p.add_argument("--output", help="Optional JSON report path.")
    return p


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
