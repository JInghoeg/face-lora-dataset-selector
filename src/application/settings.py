"""Application-wide settings independent from dataset state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Dict


SETTINGS_VERSION = 1
INFERENCE_DEVICES = ("auto", "gpu", "cpu")
THEMES = ("system", "light", "dark")


@dataclass(frozen=True)
class AppSettings:
    version: int = SETTINGS_VERSION
    inference_device: str = "auto"
    theme: str = "system"
    background_enrichment: bool = True

    @classmethod
    def from_dict(cls, value: Any) -> "AppSettings":
        data = value if isinstance(value, dict) else {}
        inference_device = str(data.get("inference_device", "auto")).lower()
        if inference_device not in INFERENCE_DEVICES:
            inference_device = "auto"

        theme = str(data.get("theme", "system")).lower()
        if theme not in THEMES:
            theme = "system"

        return cls(
            version=SETTINGS_VERSION,
            inference_device=inference_device,
            theme=theme,
            background_enrichment=bool(data.get("background_enrichment", True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SettingsService:
    """Validated application settings backed by an injected store."""

    def __init__(self, store):
        self.store = store
        self._current = AppSettings.from_dict(store.load())

    @property
    def current(self) -> AppSettings:
        return self._current

    def reload(self) -> AppSettings:
        self._current = AppSettings.from_dict(self.store.load())
        return self._current

    def update(self, **changes) -> AppSettings:
        unknown = set(changes) - {
            "inference_device",
            "theme",
            "background_enrichment",
        }
        if unknown:
            raise KeyError(
                "unknown application setting(s): " + ", ".join(sorted(unknown))
            )

        candidate = replace(self._current, **changes)
        normalized = AppSettings.from_dict(candidate.to_dict())
        self.store.save(normalized.to_dict())
        self._current = normalized
        return normalized
