"""Permanent Qt internationalization infrastructure for the UI layer."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QSettings, QTranslator, Signal


SUPPORTED_LANGUAGES = (
    ("zh_CN", "中文（简体）"),
    ("en_US", "English"),
)
_SUPPORTED_CODES = {code for code, _label in SUPPORTED_LANGUAGES}
_DEFAULT_LANGUAGE = "zh_CN"
_MANAGER = None


def _default_user_data_root() -> Path:
    return Path(
        os.environ.get("LOCALAPPDATA")
        or (Path.home() / "AppData" / "Local")
    ) / "Face LoRA Dataset Selector"


def _default_translation_root() -> Path:
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            return Path(bundle) / "translations"
        return Path(sys.executable).resolve().parent / "translations"
    return Path(__file__).resolve().parents[2] / "translations"


class LanguageManager(QObject):
    """Owns the active QTranslator and persisted UI locale."""

    languageChanged = Signal(str)
    languageLoadFailed = Signal(str, str)

    def __init__(
        self,
        app,
        *,
        settings_path: Path | None = None,
        translations_dir: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.app = app
        self.settings_path = (
            Path(settings_path)
            if settings_path is not None
            else _default_user_data_root() / "ui.ini"
        )
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(
            str(self.settings_path),
            QSettings.IniFormat,
        )
        self.translations_dir = (
            Path(translations_dir)
            if translations_dir is not None
            else _default_translation_root()
        )
        self.translator = QTranslator(self)
        self._translator_installed = False
        self._language = _DEFAULT_LANGUAGE
        self.last_error = ""

        saved = str(
            self.settings.value("ui/language", _DEFAULT_LANGUAGE)
        )
        if saved not in _SUPPORTED_CODES:
            saved = _DEFAULT_LANGUAGE
        if not self._apply(saved, emit=False):
            self._apply(_DEFAULT_LANGUAGE, emit=False)

    @property
    def language(self) -> str:
        return self._language

    def qm_path(self, language: str) -> Path:
        return self.translations_dir / f"app_{language}.qm"

    def set_language(self, language: str) -> bool:
        language = str(language)
        if language not in _SUPPORTED_CODES:
            raise ValueError(f"Unsupported UI language: {language}")
        if language == self._language:
            return True
        return self._apply(language, emit=True)

    def _remove_translator(self):
        if self._translator_installed:
            self.app.removeTranslator(self.translator)
            self._translator_installed = False

    def _apply(self, language: str, *, emit: bool) -> bool:
        previous = self._language
        self.last_error = ""

        candidate = None
        if language != _DEFAULT_LANGUAGE:
            path = self.qm_path(language)
            candidate = QTranslator(self)
            if not path.exists() or not candidate.load(str(path)):
                self.last_error = f"Translation catalog unavailable: {path}"
                self.languageLoadFailed.emit(language, self.last_error)
                return False

        # Qt emits LanguageChange synchronously while translators are
        # installed/removed. Publish the target locale first so widgets that
        # handle that event observe the new language, not the previous one.
        self._language = language

        if language == _DEFAULT_LANGUAGE:
            self._remove_translator()
        else:
            self._remove_translator()
            self.translator.deleteLater()
            self.translator = candidate
            self.app.installTranslator(self.translator)
            self._translator_installed = True

        self.settings.setValue("ui/language", language)
        self.settings.sync()

        if emit and previous != language:
            self.languageChanged.emit(language)
        return True


def initialize_i18n(
    app,
    *,
    settings_path: Path | None = None,
    translations_dir: Path | None = None,
) -> LanguageManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = LanguageManager(
            app,
            settings_path=settings_path,
            translations_dir=translations_dir,
        )
    return _MANAGER


def get_language_manager() -> LanguageManager:
    if _MANAGER is None:
        raise RuntimeError("i18n has not been initialized")
    return _MANAGER
