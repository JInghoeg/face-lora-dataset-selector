"""Shared ONNX Runtime execution-provider policy.

Feature packages request sessions through this module instead of hard-coding
CPU/GPU providers. The policy is application-configured, accelerator failure is
non-fatal, and CPU remains the mandatory fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Optional, Tuple


_ALLOWED_PREFERENCES = ("auto", "gpu", "cpu")
_ACCELERATOR_PROVIDERS = (
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
)
_CPU_PROVIDER = "CPUExecutionProvider"

_LOCK = RLock()
_preference = "auto"
_generation = 0
_last_active_provider = ""
_last_fallback_reason = ""


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


def _normalize_preference(value: Optional[str]) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in _ALLOWED_PREFERENCES:
        raise ValueError("inference preference must be auto, gpu, or cpu")
    return normalized


def configure_inference_runtime(preference: str) -> int:
    """Set provider preference and invalidate feature-local session caches."""
    global _preference, _generation
    normalized = _normalize_preference(preference)
    with _LOCK:
        if normalized != _preference:
            _preference = normalized
            _generation += 1
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


def _select_accelerator(available: Tuple[str, ...]) -> str:
    for provider in _ACCELERATOR_PROVIDERS:
        if provider in available:
            return provider
    return ""


def provider_plan(ort_module, preference: Optional[str] = None) -> ProviderPlan:
    requested = _normalize_preference(
        inference_preference() if preference is None else preference
    )
    available = _available(ort_module)

    if _CPU_PROVIDER not in available:
        raise RuntimeError("ONNX Runtime CPUExecutionProvider is unavailable.")

    if requested == "cpu":
        return ProviderPlan(requested, available, (_CPU_PROVIDER,))

    accelerator = _select_accelerator(available)
    if accelerator:
        return ProviderPlan(
            requested,
            available,
            (accelerator, _CPU_PROVIDER),
        )

    reason = (
        "GPU execution provider unavailable; using CPUExecutionProvider"
        if requested == "gpu"
        else ""
    )
    return ProviderPlan(requested, available, (_CPU_PROVIDER,), reason)


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
    accelerator_options = sess_options
    try:
        if plan.providers and plan.providers[0] == "DmlExecutionProvider":
            if accelerator_options is None:
                accelerator_options = ort_module.SessionOptions()
            accelerator_options.enable_mem_pattern = False
            accelerator_options.execution_mode = ort_module.ExecutionMode.ORT_SEQUENTIAL

        session = ort_module.InferenceSession(
            str(model_path),
            sess_options=accelerator_options,
            providers=list(plan.providers),
            **kwargs,
        )
        _record_runtime(session, plan.fallback_reason)
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
                "accelerator session failed; CPU fallback: "
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
        )
