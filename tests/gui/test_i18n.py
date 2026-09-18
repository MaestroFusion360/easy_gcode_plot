"""UI language selection and compiled translation loading."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QCoreApplication, QFile
from PyQt6.QtWidgets import QApplication

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app import i18n
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def translator(qt_app):
    i18n.uninstall_translators(qt_app)
    yield
    i18n.uninstall_translators(qt_app)


def test_language_codes_are_normalized():
    assert i18n.normalize_language("ru") == "ru"
    assert i18n.normalize_language("RU") == "ru"
    assert i18n.normalize_language("de") == "en"
    assert i18n.normalize_language(None) == "en"
    assert i18n.language_label("ru") == "Russian"


def test_compiled_translation_resource_is_packaged():
    assert QFile(":/resource/translations/app_ru.qm").exists()


def test_russian_translator_translates_form_strings(qt_app, translator):
    assert i18n.install_translator(qt_app, "ru") is True
    assert QCoreApplication.translate("OptionsDlg", "Theme") == "Тема"
    assert QCoreApplication.translate("OptionsDlg", "Russian") == "Русский"
    assert QCoreApplication.translate("MainWindow", "&File") == "&Файл"


def test_english_language_keeps_source_strings(qt_app, translator):
    assert i18n.install_translator(qt_app, "en") is False
    assert QCoreApplication.translate("OptionsDlg", "Theme") == "Theme"


def test_russian_language_translates_main_window(qt_app, translator):
    assert i18n.install_translator(qt_app, "ru") is True
    window = MainWindow()
    assert window.ui.menu_Help.title() == "&Справка"
    assert window.ui.actionToolLibrary.text() == "Библиотека инструментов"
    window.deleteLater()
