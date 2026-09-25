"""Adapter around the validated Composite detection implementation.

Kept inside the feature boundary so application/UI code does not import the
detector implementation directly.
"""
from __future__ import annotations

from .proposal import (
    CompositeProposal,
    Detection,
    PROPOSAL_VERSION,
    detect_proposal,
    proposal_from_detections,
    proposal_from_dict,
)

__all__ = [
    "CompositeProposal",
    "Detection",
    "PROPOSAL_VERSION",
    "detect_proposal",
    "proposal_from_detections",
    "proposal_from_dict",
]
