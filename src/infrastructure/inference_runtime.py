"""Shared ONNX Runtime execution-provider policy.

Feature packages request sessions through this module instead of hard-coding
CPU/GPU providers. The policy is application-configured, accelerator failure is
non-fatal, and CPU remains the mandatory fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from threading import RLock
from typing import Optional, Tuple


_ALLOWED_PREFERENCES = ("auto", "gpu", "cpu")
_ACCELERATOR_PROVIDER = "CUDAExecutionProvider"
_CPU_PROVIDER = "CPUExecutionProvider"

_LOCK = RLock()
_preference = "auto"
_generation = 0
_last_active_provider = ""
_last_fallback_reason = ""
_accelerator_prepare_attempted = False
_accelerator_prepare_error = ""
_dll_directory_handles = []


@dataclass(frozen=True)
class ProviderPlan:
    requested: str
    available: Tuple[str, ...]
    providers: Tuple[str, ...]
    fallback_reason: str = ""


@dataclass(frozen=True)
class InferenceRuntimeSnapshot:
    requested: str
    generation: int
    available: Tuple[str, ...]
    preferred: Tuple[str, ...]
    last_active_provider: str
    fallback_reason: str
    accelerator_prepare_error: str


def _normalize_preference(value: Optional[str]) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in _ALLOWED_PREFERENCES:
        raise ValueError("inference preference must be auto, gpu, or cpu")
    return normalized


def configure_inference_runtime(preference: str) -> int:
    """Set provider preference and invalidate feature-local session caches."""
    global _preference, _generation
    global _accelerator_prepare_attempted, _accelerator_prepare_error
    normalized = _normalize_preference(preference)
    with _LOCK:
        if normalized != _preference:
            _preference = normalized
            _generation += 1
            _accelerator_prepare_attempted = False
            _accelerator_prepare_error = ""
        return _generation


def inference_runtime_generation() -> int:
    with _LOCK:
        return _generation


def inference_preference() -> str:
    with _LOCK:
        return _preference


def _available(ort_module) -> Tuple[str, ...]:
    try:
        values = ort_module.get_available_providers()
    except Exception:
        values = ()
    return tuple(str(value) for value in values)


def provider_plan(ort_module, preference: Optional[str] = None) -> ProviderPlan:
    requested = _normalize_preference(
        inference_preference() if preference is None else preference
    )
    available = _available(ort_module)

    if _CPU_PROVIDER not in available:
        raise RuntimeError("ONNX Runtime CPUExecutionProvider is unavailable.")

    if requested == "cpu":
        return ProviderPlan(requested, available, (_CPU_PROVIDER,))

    if _ACCELERATOR_PROVIDER in available:
        return ProviderPlan(
            requested,
            available,
            (_ACCELERATOR_PROVIDER, _CPU_PROVIDER),
        )

    reason = (
        "CUDAExecutionProvider unavailable; using CPUExecutionProvider"
        if requested == "gpu"
        else ""
    )
    return ProviderPlan(requested, available, (_CPU_PROVIDER,), reason)


def _frozen_nvidia_bin_dirs() -> Tuple[Path, ...]:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return ()
    root = getattr(sys, "_MEIPASS", None)
    if not root:
        return ()

    base = Path(root) / "nvidia"
    components = (
        "cublas",
        "cufft",
        "cuda_runtime",
        "cuda_nvrtc",
        "curand",
        "cudnn",
    )
    return tuple(
        path
        for path in (base / component / "bin" for component in components)
        if path.is_dir()
    )


def prepare_accelerator_runtime(ort_module) -> str:
    """Make packaged/source NVIDIA runtime DLLs discoverable once per policy generation.

    Failure here is advisory. Session creation still gets a chance to use a
    system CUDA installation before the shared CPU fallback is applied.
    """
    global _accelerator_prepare_attempted, _accelerator_prepare_error
    with _LOCK:
        if _accelerator_prepare_attempted:
            return _accelerator_prepare_error
        _accelerator_prepare_attempted = True

        errors = []
        if os.name == "nt":
            add_directory = getattr(os, "add_dll_directory", None)
            if add_directory is not None:
                for path in _frozen_nvidia_bin_dirs():
                    try:
                        _dll_directory_handles.append(add_directory(str(path)))
                    except OSError as exc:
                        errors.append(f"{path.name}: {exc}")

        # ORT 1.21+ can preload NVIDIA CUDA/cuDNN wheels in normal Python
        # environments. Frozen builds use explicit DLL directories above
        # because site-packages metadata is not guaranteed to survive freezing.
        preload = getattr(ort_module, "preload_dlls", None)
        if callable(preload) and not getattr(sys, "frozen", False):
            try:
                preload(directory="")
            except Exception as exc:
                errors.append(f"preload_dlls: {exc}")

        _accelerator_prepare_error = "; ".join(errors)
        return _accelerator_prepare_error


def _record_runtime(session, fallback_reason: str = "") -> None:
    global _last_active_provider, _last_fallback_reason
    try:
        active = tuple(session.get_providers())
    except Exception:
        active = ()
    with _LOCK:
        _last_active_provider = str(active[0]) if active else ""
        _last_fallback_reason = str(fallback_reason or "")


def create_ort_session(
    ort_module,
    model_path,
    *,
    sess_options=None,
    preference: Optional[str] = None,
    **kwargs,
):
    """Create an ORT session using shared policy and safe CPU fallback."""
    plan = provider_plan(ort_module, preference)
    prepare_error = ""
    if plan.providers and plan.providers[0] == _ACCELERATOR_PROVIDER:
        prepare_error = prepare_accelerator_runtime(ort_module)
    try:
        session = ort_module.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=list(plan.providers),
            **kwargs,
        )
        _record_runtime(
            session,
            plan.fallback_reason or prepare_error,
        )
        return session
    except Exception as accelerator_error:
        if (
            plan.providers
            and plan.providers[0] != _CPU_PROVIDER
            and _CPU_PROVIDER in plan.available
        ):
            session = ort_module.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=[_CPU_PROVIDER],
                **kwargs,
            )
            _record_runtime(
                session,
                (
                    (prepare_error + "; ") if prepare_error else ""
                )
                + "accelerator session failed; CPU fallback: "
                + str(accelerator_error),
            )
            return session
        raise


def runtime_snapshot(ort_module) -> InferenceRuntimeSnapshot:
    plan = provider_plan(ort_module)
    with _LOCK:
        return InferenceRuntimeSnapshot(
            requested=plan.requested,
            generation=_generation,
            available=plan.available,
            preferred=plan.providers,
            last_active_provider=_last_active_provider,
            fallback_reason=_last_fallback_reason or plan.fallback_reason,
            accelerator_prepare_error=_accelerator_prepare_error,
        )
