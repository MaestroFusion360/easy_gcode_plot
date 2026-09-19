"""Application language selection and Qt translation loading."""

from __future__ import annotations

from PyQt6.QtCore import QLibraryInfo, QTranslator

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers the :/resource/... paths.

LANGUAGES = ("en", "ru")
LANGUAGE_LABELS = {"en": "English", "ru": "Russian"}
DEFAULT_LANGUAGE = "en"
TRANSLATION_RESOURCE = ":/resource/translations/app_{language}.qm"
# Qt ships the standard widget strings (OK/Cancel/Close, QDialogButtonBox, ...)
# in per-language catalogs.  Installing them keeps every dialog's standard
# buttons localized without per-dialog setText() calls.
QT_TRANSLATION_CATALOGS = ("qtbase",)

_installed_translators: list[QTranslator] = []


def normalize_language(value) -> str:
    """Return a supported language code, defaulting to English."""
    text = str(value or "").strip().lower()
    return text if text in LANGUAGES else DEFAULT_LANGUAGE


def language_label(language: str) -> str:
    """Return the display label for a supported language code."""
    return LANGUAGE_LABELS[normalize_language(language)]


def _install_qt_translations(app, language: str) -> None:
    """Install Qt's own catalogs so standard dialog controls are localized too."""
    translations_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for catalog in QT_TRANSLATION_CATALOGS:
        translator = QTranslator(app)
        if translator.load(f"{catalog}_{language}", translations_dir):
            app.installTranslator(translator)
            _installed_translators.append(translator)


def install_translator(app, language) -> bool:
    """Install the compiled translation for *language*; True when one was loaded."""
    language = normalize_language(language)
    if language == DEFAULT_LANGUAGE:
        return False
    translator = QTranslator(app)
    if not translator.load(TRANSLATION_RESOURCE.format(language=language)):
        return False
    _install_qt_translations(app, language)
    app.installTranslator(translator)
    _installed_translators.append(translator)
    return True


def uninstall_translators(app) -> None:
    """Remove every translator installed by :func:`install_translator`."""
    for translator in _installed_translators:
        app.removeTranslator(translator)
    _installed_translators.clear()
