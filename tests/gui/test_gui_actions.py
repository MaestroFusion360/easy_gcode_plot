"""Main-window actions and editor command behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow, QProgressBar, QToolBar

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
    assert not ui.actionOptions.icon().isNull()
    assert not ui.actionTokens.icon().isNull()
    assert not ui.actionWCS.icon().isNull()
    assert not ui.actionToolLibrary.icon().isNull()
    assert all("..." not in action.text() for action in settings_actions)

    assert ui.actionExportToolList in ui.menuCNC_Functions.actions()
    assert ui.actionExportToolList.text() == "Tool List"
    assert not ui.actionExportToolList.icon().isNull()


def test_cnc_toolbar_places_existing_commands_before_calculators(qt_app):
    window = MainWindow()
    assert window.ui.actionStock in window.ui.menuSettings.actions()
    assert not window.ui.actionStock.icon().isNull()
    actions = window.ui.cncToolBar.actions()
    expected = (
        window.ui.actionPrevToolchange,
        window.ui.actionNextToolchange,
        window.ui.menuBlockNumbers.menuAction(),
        window.ui.actionRemoveSpaces,
        window.ui.actionRemoveEmptyLines,
    )
    positions = [actions.index(action) for action in expected]
    assert positions == list(range(positions[0], positions[0] + len(expected)))
    assert actions[positions[-1] + 1] is window.ui.actionStatistics
    assert actions[positions[-1] + 2] is window.ui.actionExportToolList
    assert actions[positions[-1] + 3].isSeparator()
    assert actions[positions[-1] + 4] is getattr(window.ui, "actionHoleCalculator")
    assert [toolbar.objectName() for toolbar in window.findChildren(QToolBar)[:4]] == [
        "fileToolBar",
        "editToolBar",
        "viewToolBar",
        "cncToolBar",
    ]
    window.deleteLater()


def test_editor_case_actions_use_icons_and_change_selection_or_current_line(qt_app):
    window = MainWindow()
    editor = window.ui.editor
    assert not window.ui.actionUppercase.icon().isNull()
    assert not window.ui.actionLowercase.icon().isNull()
    assert window.ui.actionUppercase in window.ui.editToolBar.actions()
    assert window.ui.actionLowercase in window.ui.menu_Edit.actions()
    assert window.ui.actionUppercase.shortcut() == QKeySequence("Ctrl+Shift+U")
    assert window.ui.actionLowercase.shortcut() == QKeySequence("Ctrl+U")

    editor.setText("g1 x10\nM30")
    editor.setSelection(0, 0, 0, 2)
    window.ui.actionUppercase.trigger()
    assert editor.text() == "G1 x10\nM30"
    assert editor.selectedText() == "G1"
    window.ui.actionLowercase.trigger()
    assert editor.text() == "g1 x10\nM30"
    editor.setCursorPosition(1, 1)
    window.ui.actionLowercase.trigger()
    assert editor.text() == "g1 x10\nm30"
    window.ui.actionUppercase.trigger()
    assert editor.text() == "G1 X10\nM30"
    window.deleteLater()


def test_ctrl_slash_adds_one_blockskip_to_each_selected_block(qt_app):
    window = MainWindow()
    editor = window.ui.editor
    assert window.blockSkipShortcut.key() == QKeySequence("Ctrl+/")
    editor.setText("N10 G1 X1\n/N20 G1 X2\n\nN30 G1 X3\nM30")
    editor.setSelection(0, 4, 4, 0)
    window.blockSkipShortcut.activated.emit()
    assert editor.text() == "/N10 G1 X1\n/N20 G1 X2\n\n/N30 G1 X3\nM30"
    editor.undo()
    assert editor.text() == "N10 G1 X1\n/N20 G1 X2\n\nN30 G1 X3\nM30"
    editor.setCursorPosition(4, 2)
    window.ui.graphicsView.hide()
    window.show()
    editor.setFocus()
    qt_app.processEvents()
    QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
    assert editor.text().endswith("M30")
    editor.setSelection(4, 0, 4, 3)
    QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
    assert editor.text().endswith("/M30")
    window.deleteLater()


def test_ctrl_shift_slash_removes_only_selected_block_skips(qt_app):
    window = MainWindow()
    editor = window.ui.editor
    assert window.removeBlockSkipShortcut.key() == QKeySequence("Ctrl+Shift+/")
    editor.setText("/N10\n//N20\nN30\n/M30")
    editor.setSelection(0, 2, 3, 0)
    window.removeBlockSkipShortcut.activated.emit()
    assert editor.text() == "N10\n/N20\nN30\n/M30"
    editor.undo()
    assert editor.text() == "/N10\n//N20\nN30\n/M30"
    window.ui.graphicsView.hide()
    window.show()
    editor.setFocus()
    qt_app.processEvents()
    editor.setCursorPosition(3, 2)
    QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert editor.text() == "/N10\n//N20\nN30\n/M30"
    editor.setSelection(3, 0, 3, 4)
    QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert editor.text() == "/N10\n//N20\nN30\nM30"
    window.deleteLater()


def test_playback_toolbar_speed_slider_updates_timer_and_persists(qt_app):
    window = MainWindow()
    slider = window.ui.playbackSpeedSlider
    assert (slider.minimum(), slider.maximum()) == (1, 5)
    assert slider.tickInterval() == 1
    assert slider.tickPosition() == slider.TickPosition.TicksAbove
    assert slider.value() == window.playbackSpeed
    assert window.ui.playbackToolBar.widgetForAction(window.ui.playbackToolBar.actions()[-1]) is slider

    slider.setValue(5)
    assert (window.playbackSpeed, window.speedTimer) == (5, 10)
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.ui.playbackSpeedSlider.value() == 5
    restored.deleteLater()


def test_file_type_toolbar_menu_switches_the_editor_lexer(qt_app):
    window = MainWindow()
    menu = window.ui.fileTypeMenu
    actions = menu.actions()
    assert window.ui.fileTypeCombo.isHidden()
    assert window.ui.cncToolBar.widgetForAction(window.ui.cncToolBar.actions()[0]) is window.ui.fileTypeButton
    assert window.ui.fileTypeButton.menu() is menu
    assert [action.text() for action in actions] == ["Text File", "ISO G-Code"]
    assert actions[0].isChecked()
    assert not actions[0].icon().isNull()
    assert not actions[1].icon().isNull()
    assert actions[0].icon().cacheKey() != actions[1].icon().cacheKey()
    assert window.ui.fileTypeButton.icon().cacheKey() == actions[0].icon().cacheKey()

    actions[1].trigger()
    assert window.ui.fileTypeCombo.currentIndex() == 1
    assert window.ui.editor.lexer() is window.lexer
    assert actions[1].isChecked()
    assert window.ui.fileTypeButton.text() == "ISO G-Code"
    assert window.ui.fileTypeButton.icon().cacheKey() == actions[1].icon().cacheKey()

    actions[0].trigger()
    assert window.ui.fileTypeCombo.currentIndex() == 0
    assert window.ui.editor.lexer() is None
    assert actions[0].isChecked()
    assert window.ui.fileTypeButton.icon().cacheKey() == actions[0].icon().cacheKey()
    window.deleteLater()


def test_machine_specific_actions_follow_active_profile_without_restart(qt_app):
    window = MainWindow()

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    assert window.ui.actionToolLibrary.isEnabled()
    assert window.ui.menuArc_Type.isEnabled()
    assert window.ui.actionRelative_to_start.isEnabled()
    assert window.ui.actionAbsolute.isEnabled()
    assert window.ui.actionRadius_value.isEnabled()
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


def test_manual_arc_selection_overrides_auto_for_current_document(qt_app):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(True)
    window.autodetectArcType = True

    window.ui.actionAbsolute.setChecked(True)
    assert window.arc_type == 2
    assert window.autodetectArcType is True
    assert getattr(window, "_manual_arc_type_override") is True

    window.newFile()
    assert getattr(window, "_manual_arc_type_override") is False
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


def test_lathe_gcode_system_option_is_saved_and_restored(qt_app):
    window = MainWindow()
    original = window.latheGcodeSystem
    try:
        options = window.optionsDlg
        options.show()
        qt_app.processEvents()
        assert options.ui.latheGcodeSystemCombo.currentData() == original
        options.ui.latheGcodeSystemCombo.setCurrentIndex(1)
        options.accept()
        assert window.latheGcodeSystem == "B"
        assert window.settings.value("CNC/LATHE_GCODE_SYSTEM") == "B"
    finally:
        window.latheGcodeSystem = original
        window.saveSettings()
        window.deleteLater()
