"""Main-window actions and editor command behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QMainWindow, QProgressBar

from app.gcode.kernel import execute
from app.main_window import MainWindow
from app.ui.generated.main.main_ui import Ui_MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_main_ui_has_separate_options_and_tokens_settings_actions(qt_app):
    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    settings_actions = ui.menuSettings.actions()
    assert ui.actionOptions in settings_actions
    assert ui.actionTokens in settings_actions
    assert ui.actionOptions.text() == "Options"
    assert ui.actionOptions.shortcut().toString() == "F2"
    assert all("..." not in action.text() for action in settings_actions)


def test_machine_specific_actions_follow_active_profile_without_restart(qt_app):
    window = MainWindow()

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    assert window.ui.actionToolLibrary.isEnabled()
    assert not window.ui.menuArc_Type.isEnabled()
    assert not window.ui.actionRelative_to_start.isEnabled()
    assert not window.ui.actionAbsolute.isEnabled()
    assert not window.ui.actionRadius_value.isEnabled()
    assert window.optionsDlg.ui.arcToleranceSpin.isEnabled()

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert window.ui.actionToolLibrary.isEnabled()
    assert window.ui.menuArc_Type.isEnabled()
    assert window.ui.actionRelative_to_start.isEnabled()
    assert window.ui.actionAbsolute.isEnabled()
    assert window.ui.actionRadius_value.isEnabled()
    assert window.optionsDlg.ui.arcToleranceSpin.isEnabled()
    window.deleteLater()


def test_machine_specific_actions_stay_synchronized_after_new_and_load(qt_app, tmp_path):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(True)
    window.newFile()
    assert window.ui.actionToolLibrary.isEnabled()

    source = tmp_path / "sample.nc"
    source.write_text("G21 G18\nG0 X20 Z0\nM30\n", encoding="utf-8")
    window.loadFile(str(source))
    qt_app.processEvents()
    assert window.ui.actionToolLibrary.isEnabled()
    window.deleteLater()


def test_status_bar_has_no_redundant_progress_indicator(qt_app):
    window = MainWindow()

    assert not hasattr(window, "progressBar")
    assert window.ui.statusbar.findChildren(QProgressBar) == []
    window.deleteLater()


def test_status_bar_execution_groups_are_spaced_and_diagnostics_are_explicit(qt_app):
    window = MainWindow()
    result = execute("G0 X20 Z0\nG2 X40 Z0 R1\nM30")
    window.updateExecutionStatus(result=result, elapsed_ms=110457.158)

    assert all(
        label.contentsMargins().left() >= 7
        for label in (
            window.executionStatusLabel,
            window.modeStatusLabel,
            window.unitsStatusLabel,
            window.sourceStatusLabel,
            window.traceStatusLabel,
            window.diagnosticsStatusLabel,
            window.timeStatusLabel,
        )
    )
    assert window.diagnosticsStatusLabel.text() == "Errors: 1"
    assert "INVALID_GEOMETRY" in window.diagnosticsStatusLabel.toolTip()
    assert window.timeStatusLabel.text() == "Exec: 110.46 s"
    window.deleteLater()


def test_block_number_dialog_applies_values_only_on_ok(qt_app):
    window = MainWindow()
    dialog = window.blockNumDlg
    original = (window.seqNumStart, window.seqNumIncr, window.seqNumSpacing)
    calls = []
    window.renumber = lambda: calls.append(True)

    dialog.show()
    dialog.ui.startSpinBox.setValue(original[0] + 10)
    dialog.ui.intervSpinBox.setValue(original[1] + 2)
    dialog.ui.spacingCmbBox.setCurrentIndex(0 if original[2] else 1)
    dialog.reject()
    assert (window.seqNumStart, window.seqNumIncr, window.seqNumSpacing) == original
    assert calls == []

    dialog.show()
    dialog.ui.startSpinBox.setValue(original[0] + 10)
    dialog.ui.intervSpinBox.setValue(original[1] + 2)
    dialog.ui.spacingCmbBox.setCurrentIndex(0 if original[2] else 1)
    dialog.accept()
    assert (window.seqNumStart, window.seqNumIncr, window.seqNumSpacing) == (
        original[0] + 10,
        original[1] + 2,
        not original[2],
    )
    assert calls == [True]
    window.deleteLater()


def test_toolchange_navigation_skips_comments_and_wraps(qt_app):
    window = MainWindow()
    window.ui.editor.setText("(T9999)\nT0101 M6\nG0 X10\n; T8888\nN20T0202\n")
    window.ui.editor.setCursorPosition(0, 0)

    assert window.nextToolchange()
    assert window.ui.editor.selectedText() == "T0101"
    assert window.nextToolchange()
    assert window.ui.editor.selectedText() == "T0202"
    assert window.nextToolchange()
    assert window.ui.editor.selectedText() == "T0101"
    assert window.previousToolchange()
    assert window.ui.editor.selectedText() == "T0202"
    window.deleteLater()


def test_editor_context_menu_contains_edit_then_all_cnc_actions(qt_app, monkeypatch):
    window = MainWindow()
    captured = []

    class Menu:
        def __init__(self, _parent):
            pass

        def addActions(self, actions):
            captured.append(list(actions))

        def addSeparator(self):
            captured.append("separator")

        def exec(self, _point):
            pass

    monkeypatch.setattr("app.ui.windows.main_window_editor_ops.QMenu", Menu)
    window.editorContextMenu(QPoint())

    assert captured == [
        window.ui.menu_Edit.actions(),
        "separator",
        window.ui.menuCNC_Functions.actions(),
    ]
    window.deleteLater()


def test_find_replace_and_replace_all_preserve_editor_state(qt_app, monkeypatch):
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.editor.setText("g1 x1\nG1 X2\n")
    window.ui.editor.setCursorPosition(0, 0)
    assert window.find("g1", True, True, False) is True
    window.replace("G1", "G0", False, True, False)
    assert window.ui.editor.text().startswith("G0 x1")

    window.ui.editor.setCursorPosition(1, 2)
    assert window.replaceAll("g1", "G2", False, True) == 1
    assert window.ui.editor.getCursorPosition() == (1, 2)
    window.ui.editor.undo()
    assert window.ui.editor.text() == "G0 x1\nG1 X2\n"

    monkeypatch.setattr("app.ui.windows.main_window_editor_ops.QMessageBox.information", lambda *_args: None)
    window.ui.editor.setSelection(0, 0, 0, 2)
    assert window.find("NOT_FOUND", False, False, True) is False
    assert window.ui.editor.getSelection() == (0, 0, 0, 2)
    assert window.find("", False, False, True) is False
    window.deleteLater()


def test_main_window_actions_open_the_reused_dialog_instances(qt_app):
    window = MainWindow()
    tokens = window.tokensDlg
    options = window.optionsDlg
    window.ui.actionTokens.trigger()
    window.ui.actionOptions.trigger()
    qt_app.processEvents()
    assert tokens.isVisible()
    assert options.isVisible()
    assert window.tokensDlg is tokens
    assert window.optionsDlg is options
    tokens.close()
    options.close()
    window.deleteLater()
