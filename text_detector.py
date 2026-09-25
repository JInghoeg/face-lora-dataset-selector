"""Compatibility shim.

Text detection is owned by features.text_cleanup. New product code must import
through that feature/application boundary.
"""
from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

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
