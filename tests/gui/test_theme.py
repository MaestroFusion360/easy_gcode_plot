"""Dark/light theme palette, editor colors, and standard plot color mapping."""

# pylint: disable=protected-access
from __future__ import annotations

import pytest
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyle

from app import theme
from app.main_window import MainWindow
from app.ui.support.lexer import GcodeLexer

LINE_NUMBER_STYLE = 33


def _scintilla_style_back(editor, style):
    """Return a Scintilla style background as '#rrggbb' (stored as 0xBBGGRR)."""
    value = editor.SendScintilla(QsciScintilla.SCI_STYLEGETBACK, style) & 0xFFFFFF
    red = value & 0xFF
    green = (value >> 8) & 0xFF
    blue = (value >> 16) & 0xFF
    return QColor(red, green, blue).name()


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def restore_light_theme(qt_app):
    yield
    if theme.current_theme() != "light":
        theme.reset_theme_state()
        theme.apply_application_theme(qt_app, "light")


@pytest.fixture
def capture_application_theme(monkeypatch):
    applied = []
    monkeypatch.setattr(theme, "apply_application_theme", lambda _app, name: applied.append(name))
    return applied


def test_theme_names_are_normalized():
    assert theme.normalize_theme("dark") == "dark"
    assert theme.normalize_theme("DARK") == "dark"
    assert theme.normalize_theme("nonsense") == "light"
    assert theme.normalize_theme(None) == "light"


def test_dark_palette_is_dark_and_light_standard_palette_is_not():
    dark = theme._dark_palette()
    assert dark.color(QPalette.ColorRole.Window).name() == "#1f1f1f"
    assert dark.color(QPalette.ColorRole.Base).name() == "#252526"
    assert dark.color(QPalette.ColorRole.Text).name() == "#e6e6e6"
    assert QApplication.style().standardPalette().color(QPalette.ColorRole.Window).name() != "#1f1f1f"


def test_light_theme_keeps_the_platform_style(qt_app):
    theme.reset_theme_state()
    before = qt_app.style().objectName()
    theme.apply_application_theme(qt_app, "light")
    assert qt_app.style().objectName() == before
    assert qt_app.styleSheet() == ""


def test_dark_and_light_keep_platform_geometry(qt_app, monkeypatch):
    # The normal path (including Windows 11) keeps the native style.  Windows
    # 10 has a separate compatibility path tested below.
    monkeypatch.setattr(theme, "_needs_windows_dark_compatibility", lambda *_args: False)
    theme.reset_theme_state()
    style_name = qt_app.style().objectName()
    font = qt_app.font().toString()
    metrics = {
        metric: qt_app.style().pixelMetric(metric)
        for metric in (
            QStyle.PixelMetric.PM_MenuHMargin,
            QStyle.PixelMetric.PM_MenuVMargin,
            QStyle.PixelMetric.PM_MenuBarHMargin,
            QStyle.PixelMetric.PM_MenuBarVMargin,
            QStyle.PixelMetric.PM_MenuPanelWidth,
        )
    }

    theme.apply_application_theme(qt_app, "dark")
    assert qt_app.style().objectName() == style_name
    assert qt_app.font().toString() == font
    assert {metric: qt_app.style().pixelMetric(metric) for metric in metrics} == metrics

    theme.apply_application_theme(qt_app, "light")
    assert qt_app.style().objectName() == style_name
    assert qt_app.font().toString() == font
    assert {metric: qt_app.style().pixelMetric(metric) for metric in metrics} == metrics


def test_native_dark_theme_never_replaces_style_or_stylesheet(qt_app, monkeypatch):
    set_style_calls = []
    set_stylesheet_calls = []
    monkeypatch.setattr(theme, "_needs_windows_dark_compatibility", lambda *_args: False)
    monkeypatch.setattr(qt_app, "setStyle", lambda *args, **kwargs: set_style_calls.append((args, kwargs)))
    monkeypatch.setattr(qt_app, "setStyleSheet", set_stylesheet_calls.append)

    theme.reset_theme_state()
    theme.apply_application_theme(qt_app, "dark")

    assert set_style_calls == []
    assert set_stylesheet_calls == []
    theme.apply_application_theme(qt_app, "light")


def test_windows_dark_compatibility_targets_legacy_styles_only():
    assert theme._needs_windows_dark_compatibility("win32", "windowsvista") is True
    assert theme._needs_windows_dark_compatibility("win32", "windows") is True
    assert theme._needs_windows_dark_compatibility("win32", "windows11") is False
    assert theme._needs_windows_dark_compatibility("linux", "windowsvista") is False


def test_windows_legacy_style_forces_dark_palette_even_when_scheme_is_reported(qt_app, monkeypatch):
    palettes = []
    monkeypatch.setattr(theme, "_set_color_scheme", lambda _app, _target: True)
    monkeypatch.setattr(theme, "_needs_windows_dark_compatibility", lambda *_args: True)
    monkeypatch.setattr(theme, "_enable_windows_dark_compatibility", lambda _app: None)
    monkeypatch.setattr(qt_app, "setPalette", palettes.append)

    theme.reset_theme_state()
    theme.apply_application_theme(qt_app, "dark")

    assert len(palettes) == 1
    assert palettes[0].color(QPalette.ColorRole.Window).name() == "#1f1f1f"


def test_dark_theme_uses_palette_only_as_color_scheme_fallback(qt_app, monkeypatch):
    palettes = []
    monkeypatch.setattr(theme, "_set_color_scheme", lambda _app, _target: False)
    monkeypatch.setattr(qt_app, "setPalette", palettes.append)

    theme.reset_theme_state()
    theme.apply_application_theme(qt_app, "dark")

    assert len(palettes) == 1
    assert palettes[0].color(QPalette.ColorRole.Window).name() == "#1f1f1f"


def test_editor_theme_sets_lexer_background(qt_app):
    editor = QsciScintilla()
    lexer = GcodeLexer(editor)
    editor.setLexer(lexer)
    theme.apply_editor_theme(editor, lexer, "dark")
    assert _scintilla_style_back(editor, 0) == theme.editor_colors("dark")["paper"]
    theme.apply_editor_theme(editor, lexer, "light")
    assert _scintilla_style_back(editor, 0) == "#ffffff"


def test_themed_plot_value_keeps_custom_colors_and_moves_defaults():
    assert theme.themed_plot_value("#0000ff", "linear", "dark") == theme.plot_defaults("dark")["linear"]
    assert theme.themed_plot_value("#6fa8ff", "linear", "light") == theme.plot_defaults("light")["linear"]
    assert theme.themed_plot_value("#123456", "linear", "dark") == "#123456"


def test_editor_theme_sets_paper_and_lexer_colors(qt_app):
    editor = QsciScintilla()
    lexer = GcodeLexer(editor)
    theme.apply_editor_theme(editor, lexer, "dark")
    dark = theme.editor_colors("dark")
    assert editor.paper().name() == QColor(dark["paper"]).name()
    assert lexer.color(lexer.Rapid).name() == QColor(dark["rapid"]).name()
    theme.apply_editor_theme(editor, lexer, "light")
    assert lexer.color(lexer.Rapid).name() == QColor("#ff0000").name()


def test_main_window_loads_dark_theme_from_settings(qt_app, capture_application_theme):
    window = MainWindow()
    window.settings.setValue("GENERAL/THEME", "dark")
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.uiTheme == "dark"
    assert capture_application_theme[-1] == "dark"
    assert restored.plotBackground == theme.plot_defaults("dark")["background"]
    assert restored.ui.editor.paper().name() == theme.editor_colors("dark")["paper"].lower()
    restored.deleteLater()


def test_main_window_keeps_custom_plot_colors_in_dark_theme(qt_app, capture_application_theme):
    window = MainWindow()
    window.settings.setValue("GENERAL/THEME", "dark")
    window.settings.setValue("PLOT/LINE_COLOR", "#123456")
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.uiTheme == "dark"
    assert restored.plotLineColor == "#123456"
    restored.deleteLater()


def test_options_theme_change_moves_standard_plot_colors(qt_app, capture_application_theme):
    window = MainWindow()
    window.uiTheme = "light"
    for key, attribute in theme.PLOT_COLOR_ATTRIBUTES.items():
        setattr(window, attribute, theme.plot_defaults("light")[key])
    dialog = window.optionsDlg
    dialog.load_values()
    dialog.ui.themeCombo.setCurrentIndex(1)
    dialog.accept()

    assert window.uiTheme == "dark"
    assert window.plotBackground == theme.plot_defaults("dark")["background"]
    assert window.plotGridColor == theme.plot_defaults("dark")["grid"]
    window.deleteLater()


def test_switching_file_type_keeps_dark_editor_chrome(qt_app, capture_application_theme):
    window = MainWindow()
    window.uiTheme = "dark"
    window.applyUiTheme()
    dark = theme.editor_colors("dark")

    window.changeFileType(1)
    assert _scintilla_style_back(window.ui.editor, 0) == dark["paper"]
    assert _scintilla_style_back(window.ui.editor, LINE_NUMBER_STYLE) == dark["margin_background"]

    window.changeFileType(0)
    assert _scintilla_style_back(window.ui.editor, 0) == dark["paper"]
    assert _scintilla_style_back(window.ui.editor, LINE_NUMBER_STYLE) == dark["margin_background"]
    window.deleteLater()
