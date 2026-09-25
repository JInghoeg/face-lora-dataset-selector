"""Repository launcher and compatibility import surface.

Product implementation lives under src/. Keep this file intentionally tiny so
source users can continue to run python app.py and existing tests/tools that
import app keep working.
"""
from __future__ import annotations

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app_main import *  # noqa: F401,F403
from app_main import main as _main

if __name__ == "__main__":
    _main()
