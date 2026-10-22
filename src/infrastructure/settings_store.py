"""Portable JSON storage for application-wide settings."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


class JsonSettingsStore:
    """Small atomic JSON store.

    This store is intentionally schema-agnostic. Application policy and
    validation live in application.settings; infrastructure only owns durable
    portable I/O.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def save(self, value: Dict[str, Any]) -> None:
        if not isinstance(value, dict):
            raise TypeError("settings payload must be a dict")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(str(temporary), str(self.path))
