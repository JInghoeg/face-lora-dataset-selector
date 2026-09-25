"""Cooperative cancellation primitives shared by application/features."""
from __future__ import annotations


class OperationCancelled(RuntimeError):
    """Raised at safe checkpoints when a background operation is cancelled."""


def check_cancelled(cancelled=None) -> None:
    if cancelled is not None and cancelled():
        raise OperationCancelled("Operation cancelled")
