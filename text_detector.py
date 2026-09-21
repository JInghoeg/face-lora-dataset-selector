"""Compatibility shim.

Text detection is owned by features.text_cleanup. New product code must import
through that feature/application boundary.
"""
from features.text_cleanup.detector import (
    DBPostProcess,
    DetPreProcess,
    ResizeImgError,
    TextDetector,
)

__all__ = [
    "DBPostProcess",
    "DetPreProcess",
    "ResizeImgError",
    "TextDetector",
]
