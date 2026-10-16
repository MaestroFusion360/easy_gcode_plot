"""Native editor styles and Options integration, without CNC execution."""

# pylint: disable=protected-access

from pathlib import Path

import pytest
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.support.heidenhain_lexer import HeidenhainLexer


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _style(editor, text, token):
    position = len(text[: text.index(token)].encode("utf-8"))
    return editor.SendScintilla(editor.SCI_GETSTYLEAT, position)


def test_native_styles_comments_and_partial_utf8_recolor(qt_app):
    editor = QsciScintilla()
    lexer = HeidenhainLexer(editor)
    editor.setLexer(lexer)
    text = (
        '0 BEGIN PGM "деталь;1" MM\r\n'
        "1 L X+0 FMAX ; быстрый\r\n"
        "2 L X+Q1 F120 (подача)\r\n"
        "3 CC X0 Y0\r\n"
        "; комментарий\r\n"
        "4 C X10 Y0 DR+\r\n"
        "5 X20\r\n"
        "/6 L X0 FMAX\r\n"
    )
    editor.setText(text)
    lexer.styleText(0, editor.length())
    expected = {
        "деталь": lexer.Default,
        "L X+0": lexer.Rapid,
        "; быстрый": lexer.Comment,
        "L X+Q1": lexer.Linear,
        "(подача)": lexer.Comment,
        "CC X0": lexer.Circular,
        "комментарий": lexer.Comment,
        "C X10": lexer.Circular,
        "X20": lexer.Circular,
        "/6": lexer.Comment,
    }
    for token, style in expected.items():
        assert _style(editor, text, token) == style
    start = len(text[: text.index("X20")].encode("utf-8"))
    lexer.styleText(start, editor.length())
    assert _style(editor, text, "X20") == lexer.Circular
    editor.setText("X1\n")
    lexer.styleText(0, editor.length())
    assert _style(editor, editor.text(), "X1") == lexer.Rapid
    editor.deleteLater()


@pytest.mark.parametrize("dark", [False, True])
def test_options_select_and_persist_native_lexer(qt_app, dark):
    window = MainWindow()
    try:
        original_lexer = window.ui.editor.lexer()
        original_file_type = window.ui.fileTypeCombo.currentIndex()
        dialog = window.optionsDlg
        dialog.load_values()
        dialog.ui.fileTypeCombo.setCurrentIndex(2)
        dialog.accept()
        assert window.defaultFileType == 2
        assert window.ui.fileTypeCombo.currentIndex() == original_file_type
        assert window.ui.editor.lexer() is original_lexer
        window.newFile()
        assert window.ui.fileTypeCombo.currentIndex() == 2
        assert window.ui.editor.lexer() is window.heidenhainLexer
        window.uiTheme = "dark" if dark else "light"
        window.editorRapidColor = "#ab1234"
        window.applyUiTheme()
        assert window.heidenhainLexer.color(window.heidenhainLexer.Rapid).name() == "#ab1234"
        assert window.heidenhainLexer.defaultPaper() == window.lexer.defaultPaper()
        window.saveSettings()
    finally:
        window.deleteLater()
    restored = MainWindow()
    try:
        assert restored.defaultFileType == 2
        assert restored.ui.editor.lexer() is restored.heidenhainLexer
        assert restored.heidenhainLexer.color(restored.heidenhainLexer.Rapid).name() == "#ab1234"
    finally:
        restored.deleteLater()


def test_open_h_selects_native_execution_and_keeps_mdi_highlighting(qt_app, monkeypatch):
    window = MainWindow()
    try:
        window.autoUpdateEnabled = False
        window.ui.fileTypeCombo.setCurrentIndex(1)
        window.ui.editor.setText("G0 X1\n")
        iso_document = window._documents[window._active_document_index]
        window.ui.actionLatheMode.setChecked(True)
        path = Path(__file__).resolve().parents[1] / "fixtures/milling/heidenhain/sample.h"
        monkeypatch.setattr(window, "scheduleAutoUpdate", lambda **_kwargs: None)
        assert window.loadFile(str(path))
        assert not window.latheMode
        assert window._document_source_dialect == "heidenhain"
        assert window.ui.editor.lexer() is window.heidenhainLexer
        result, points, limited = window._calculate_editor_source(show_errors=False, show_dialog=False, render=True)
        assert result.ok and result.complete and len(result.motions) == 3958
        assert points and not limited
        native_document = window._documents[window._active_document_index]
        assert window._activate_document(window._documents.index(iso_document))
        assert window.ui.editor.lexer() is window.lexer
        assert window._activate_document(window._documents.index(native_document))
        assert window.ui.editor.lexer() is window.heidenhainLexer
        assert window._document_source_dialect == "heidenhain"
    finally:
        window.deleteLater()
