"""Options dialog and persisted runtime settings."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor, QKeySequence
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.main_window import MainWindow
from app.settings import get_settings
from app.ui.dialogs.hotkey_assignment import HotkeyAssignmentDialog
from app.ui.dialogs.options import OptionsDialog
from app.ui.support.hotkeys import menu_commands
from app.ui.windows.main_window_execution import playback_interval_ms, playback_speed_level


def test_view_hotkeys_can_be_changed_and_restored(qt_app):
    window = MainWindow()
    assert window.ui.actionRefresh in window.ui.viewToolBar.actions()
    assert window.ui.actionRefresh not in window.ui.cncToolBar.actions()
    commands = list(menu_commands(window))
    assert len(commands) > 30
    assert {"actionStock", "actionToolLibrary", "actionSnippets", "actionRenumber"}.issubset(window.hotkeys)
    for action_name, default in (
        ("actionRefresh", "F5"),
        ("action3D", "Ctrl+1"),
        ("actionTop", "Ctrl+2"),
        ("actionFront", "Ctrl+3"),
        ("actionLeft", "Ctrl+4"),
    ):
        assert window.hotkeys[action_name] == default
        assert getattr(window.ui, action_name).shortcut() == QKeySequence(default)

    dialog = window.optionsDlg
    dialog.load_values()
    assert dialog.ui.hotkeysTable.rowCount() == len(commands)
    assert dialog.hotkeyEditor.assign("actionRefresh", "Ctrl+Shift+R")
    assert dialog.hotkeyEditor.assign("actionToolLibrary", "Ctrl+Alt+L")
    dialog.accept()
    assert window.ui.actionRefresh.shortcut() == QKeySequence("Ctrl+Shift+R")
    assert window.ui.actionToolLibrary.shortcut() == QKeySequence("Ctrl+Alt+L")
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.ui.actionRefresh.shortcut() == QKeySequence("Ctrl+Shift+R")
    assert restored.ui.actionToolLibrary.shortcut() == QKeySequence("Ctrl+Alt+L")
    restored.optionsDlg.restore_defaults()
    restored.optionsDlg.accept()
    assert restored.ui.actionRefresh.shortcut() == QKeySequence("F5")
    assert restored.ui.actionToolLibrary.shortcut().isEmpty()
    restored.deleteLater()


def test_hotkey_assignment_dialog_builds_shortcut_from_controls(qt_app, monkeypatch):
    dialog = HotkeyAssignmentDialog("Open", "Ctrl+O", {})
    assert dialog.ui.commandEdit.text() == "Open"
    assert dialog.ui.ctrlCheck.isChecked()
    assert dialog.ui.keyCombo.currentText() == "O"
    dialog.ui.altCheck.setChecked(True)
    assert dialog.shortcut() == "Ctrl+Alt+O"
    dialog.ui.keyCombo.setCurrentIndex(0)
    assert dialog.shortcut() == ""

    warnings = []
    monkeypatch.setattr("app.ui.dialogs.hotkey_assignment.QMessageBox.warning", lambda *args: warnings.append(args))
    occupied = HotkeyAssignmentDialog("Open", "Ctrl+O", {"Ctrl+O": "New"})
    occupied.accept()
    assert warnings
    assert occupied.result() == 0

    occupied.ui.keyCombo.setEditText("not a key")
    occupied.accept()
    assert len(warnings) == 2
    assert occupied.result() == 0


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_options_dialog_is_independent_and_exposes_language_and_theme(qt_app):
    parent = QMainWindow()
    dialog = OptionsDialog(parent)
    assert dialog.parent() is parent
    assert dialog.windowTitle() == "Options"
    assert dialog.ui.buttonBox.button(dialog.ui.buttonBox.StandardButton.RestoreDefaults) is not None
    assert dialog.ui.languageCombo.count() == 2
    assert dialog.ui.languageCombo.isEnabled() is True
    assert dialog.ui.themeCombo.count() == 2
    assert dialog.ui.themeCombo.isEnabled() is True
    assert [dialog.ui.toolpanelIconsCombo.itemText(index) for index in range(3)] == [
        "Large 32x32",
        "Medium 24x24",
        "Small 16x16",
    ]
    assert dialog.ui.toolpanelIconsCombo.currentIndex() == 1
    assert [dialog.ui.commentStyleCombo.itemText(index) for index in range(2)] == [
        "Parentheses ()",
        "Semicolon ;",
    ]


def test_toolbar_icon_size_applies_to_all_panels_and_persists(qt_app):
    window = MainWindow()
    assert window.toolbarIconSize == 24
    dialog = window.optionsDlg
    dialog.load_values()
    dialog.ui.toolpanelIconsCombo.setCurrentIndex(0)
    dialog.accept()
    assert window.toolbarIconSize == 32
    toolbar_names = ("fileToolBar", "editToolBar", "cncToolBar", "viewToolBar", "playbackToolBar")
    assert all(getattr(window.ui, name).iconSize().width() == 32 for name in toolbar_names)
    assert getattr(window.ui, "actionHoleCalculator").icon().pixmap(32, 32).width() == 32
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.toolbarIconSize == 32
    assert all(getattr(restored.ui, name).iconSize().width() == 32 for name in toolbar_names)
    restored.deleteLater()


@pytest.mark.parametrize("level, interval", [(1, 1000), (2, 250), (3, 100), (4, 40), (5, 10)])
def test_playback_speed_uses_cnc_editor_intervals(level, interval):
    assert playback_interval_ms(level) == interval
    assert playback_speed_level(interval) == level


def test_legacy_timer_interval_migrates_to_playback_speed_level(qt_app):
    window = MainWindow()
    window.settings.remove("PLOT/PLAYBACK_SPEED")
    window.settings.setValue("PLOT/TIMER_SPEED", 40)
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.playbackSpeed == 4
    assert restored.speedTimer == 40
    restored.deleteLater()


def test_options_defaults_and_color_picker(qt_app, monkeypatch):
    window = MainWindow()
    dialog = window.optionsDlg
    dialog.ui.linearColorEdit.setText("#123456")
    dialog.restore_defaults()
    assert dialog.ui.autoUpdateCheck.isChecked()
    assert dialog.ui.autoUpdateMaxSegmentsSpin.value() == 20000
    assert dialog.ui.maxGeneratedMotionsSpin.value() == 200000
    assert dialog.ui.autodetectArcTypeCheck.isChecked()
    assert not dialog.ui.ignoreBlockSkipCheck.isChecked()
    assert dialog.ui.linearColorEdit.text() == "#0000ff"
    assert dialog.ui.toolColorEdit.text() == "#4d99ff"
    assert dialog.ui.stlColorEdit.text() == "#b0b0b0"
    assert not dialog.ui.backgroundGradientCheck.isChecked()
    assert not dialog.ui.stlWireframeCheck.isChecked()
    assert dialog.ui.axesCheck.isChecked()
    assert dialog.ui.gridStepSpin.value() == 0
    assert dialog.ui.playbackSpeedSlider.value() == 3
    assert dialog.ui.arcSamplingPresetCombo.currentText() == "Normal"
    assert dialog.ui.arcToleranceSpin.value() == pytest.approx(0.002)
    assert dialog.ui.maximumCircularRadiusSpin.value() == pytest.approx(1000.0)
    assert dialog.ui.minimumCircularRadiusSpin.value() == pytest.approx(0.01)
    assert dialog.ui.minimumChordLengthSpin.value() == pytest.approx(0.25)
    monkeypatch.setattr("app.ui.dialogs.options.QColorDialog.getColor", lambda *args: QColor("#abcdef"))
    dialog.ui.arcColorButton.click()
    assert dialog.ui.arcColorEdit.text() == "#abcdef"
    window.deleteLater()


def test_arc_sampling_preset_populates_all_limits(qt_app):
    window = MainWindow()
    dialog = window.optionsDlg
    dialog.ui.arcSamplingPresetCombo.setCurrentIndex(3)

    assert dialog.ui.arcToleranceSpin.value() == pytest.approx(0.05)
    assert dialog.ui.maximumCircularRadiusSpin.value() == pytest.approx(250.0)
    assert dialog.ui.minimumCircularRadiusSpin.value() == pytest.approx(0.1)
    assert dialog.ui.minimumChordLengthSpin.value() == pytest.approx(2.5)
    window.deleteLater()


def test_arc_sampling_settings_persist_in_config(qt_app):
    window = MainWindow()
    window.arcSamplingPreset = "large"
    window.arcTolerance = 0.01
    window.maximumCircularRadius = 500.0
    window.minimumCircularRadius = 0.05
    window.minimumChordLength = 1.0
    window.saveSettings()
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.arcSamplingPreset == "large"
    assert restored.arcTolerance == pytest.approx(0.01)
    assert restored.maximumCircularRadius == pytest.approx(500.0)
    assert restored.minimumCircularRadius == pytest.approx(0.05)
    assert restored.minimumChordLength == pytest.approx(1.0)
    restored.deleteLater()


def test_autodetect_arc_type_defaults_on_and_persists(qt_app):
    settings = get_settings()
    settings.remove("CNC/AUTODETECT_ARC_TYPE")
    settings.sync()

    window = MainWindow()
    assert window.autodetectArcType is True
    assert window.optionsDlg.ui.autodetectArcTypeCheck.isChecked()
    window.autodetectArcType = False
    window.saveSettings()
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.autodetectArcType is False
    restored.optionsDlg.load_values()
    assert not restored.optionsDlg.ui.autodetectArcTypeCheck.isChecked()
    restored.deleteLater()


def test_ignore_block_skip_defaults_off_and_persists(qt_app):
    settings = get_settings()
    settings.remove("CNC/IGNORE_BLOCK_SKIP")
    settings.sync()

    window = MainWindow()
    assert window.ignoreBlockSkip is False
    assert not window.optionsDlg.ui.ignoreBlockSkipCheck.isChecked()
    window.ignoreBlockSkip = True
    window.saveSettings()
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.ignoreBlockSkip is True
    restored.optionsDlg.load_values()
    assert restored.optionsDlg.ui.ignoreBlockSkipCheck.isChecked()
    restored.deleteLater()


def test_generated_motion_limit_defaults_and_persists(qt_app):
    settings = get_settings()
    settings.remove("GENERAL/MAX_GENERATED_MOTIONS")
    settings.sync()

    window = MainWindow()
    assert window.maxGeneratedMotions == 200000
    window.maxGeneratedMotions = 345678
    window.saveSettings()
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.maxGeneratedMotions == 345678
    restored.optionsDlg.load_values()
    assert restored.optionsDlg.ui.maxGeneratedMotionsSpin.value() == 345678
    restored.deleteLater()


def test_options_apply_every_runtime_plot_control(qt_app, monkeypatch):
    window = MainWindow()
    dialog = window.optionsDlg
    saved = []
    refreshed = []
    stl_refreshed = []
    monkeypatch.setattr(window, "saveSettings", lambda: saved.append(True))
    monkeypatch.setattr(window, "refreshPlotView", lambda: refreshed.append(True))
    monkeypatch.setattr(window, "refreshStlAppearance", lambda: stl_refreshed.append(True))
    dialog.load_values()
    dialog.ui.rapidColorEdit.setText("#110000")
    dialog.ui.linearColorEdit.setText("#001100")
    dialog.ui.arcColorEdit.setText("#000011")
    dialog.ui.currentColorEdit.setText("#111111")
    dialog.ui.toolColorEdit.setText("#224466")
    dialog.ui.backgroundColorEdit.setText("#eeeeee")
    dialog.ui.backgroundGradientCheck.setChecked(True)
    dialog.ui.stlColorEdit.setText("#abcdef")
    dialog.ui.stlWireframeCheck.setChecked(True)
    dialog.ui.lineWidthSpin.setValue(2.5)
    dialog.ui.gridStepSpin.setValue(12.5)
    dialog.ui.axesCheck.setChecked(False)
    dialog.ui.gridCheck.setChecked(True)
    dialog.ui.arcToleranceSpin.setValue(0.02)
    dialog.ui.correctionCheck.setChecked(False)
    dialog.ui.ignoreBlockSkipCheck.setChecked(True)
    dialog.ui.commentStyleCombo.setCurrentIndex(1)
    dialog.ui.autoUpdateCheck.setChecked(False)
    dialog.ui.autoUpdateMaxSegmentsSpin.setValue(7500)
    dialog.ui.maxGeneratedMotionsSpin.setValue(350000)
    dialog.ui.playbackSpeedSlider.setValue(5)
    dialog.accept()
    assert (window.plotRapidColor, window.plotLineColor, window.plotArcColor, window.plotCurrentColor) == (
        "#110000",
        "#001100",
        "#000011",
        "#111111",
    )
    assert window.plotToolColor == "#224466"
    assert window.plotBackground == "#eeeeee"
    assert window.plotBackgroundGradient is True
    assert window.stlColor == "#abcdef"
    assert window.stlWireframe is True
    assert window.plotLineWidth == 2.5
    assert window.plotGridStep == 12.5
    assert window.plotAxes is False
    assert window.plotGrid is True and window.ui.actionGrid.isChecked()
    assert window.arcTolerance == 0.02
    assert window.correctionEnabled is False
    assert window.ignoreBlockSkip is True
    assert window.commentStyle == "semicolon"
    assert (window.co, window.ci) == (";", "")
    assert window.lexer.comment_style == "semicolon"
    assert window.autoUpdateEnabled is False
    assert window.autoUpdateMaxSegments == 7500
    assert window.maxGeneratedMotions == 350000
    assert window.playbackSpeed == 5
    assert window.speedTimer == 10
    assert saved == [True] and stl_refreshed == [True] and refreshed == [True]
    window.deleteLater()


def test_stl_and_gradient_plot_options_are_persisted(qt_app):
    window = MainWindow()
    window.plotBackgroundGradient = True
    window.stlColor = "#2468ac"
    window.plotToolColor = "#123abc"
    window.playbackSpeed = 4
    window.speedTimer = 40
    window.stlWireframe = True
    window.saveSettings()
    window.settings.sync()

    restored = MainWindow()
    assert restored.plotBackgroundGradient is True
    assert restored.stlColor == "#2468ac"
    assert restored.plotToolColor == "#123abc"
    assert restored.playbackSpeed == 4
    assert restored.speedTimer == 40
    assert restored.stlWireframe is True
    window.deleteLater()
    restored.deleteLater()


def test_legacy_grid_color_is_migrated_for_gradient_contrast(qt_app):
    window = MainWindow()
    window.settings.setValue("PLOT/GRID_COLOR", "#d3d3d3")
    window.settings.sync()
    window.deleteLater()

    restored = MainWindow()
    assert restored.plotGridColor == "#808080"
    restored.deleteLater()


@pytest.mark.parametrize("changed_option", ["units", "correction", "tolerance", "block_skip"])
def test_options_runtime_semantic_changes_reexecute_current_document(qt_app, monkeypatch, changed_option):
    window = MainWindow()
    dialog = window.optionsDlg
    dialog.load_values()
    window.execution_result = object()
    updated = []
    refreshed = []
    monkeypatch.setattr(window, "updateData", lambda: updated.append(True) or True)
    monkeypatch.setattr(window, "refreshPlotView", lambda: refreshed.append(True))
    monkeypatch.setattr(window, "saveSettings", lambda: None)

    if changed_option == "units":
        dialog.ui.unitsCombo.setCurrentIndex(1 if window.defaultUnits == "mm" else 0)
    elif changed_option == "correction":
        dialog.ui.correctionCheck.setChecked(not window.correctionEnabled)
    elif changed_option == "block_skip":
        dialog.ui.ignoreBlockSkipCheck.setChecked(not window.ignoreBlockSkip)
    else:
        dialog.ui.arcToleranceSpin.setValue(window.arcTolerance * 2.0)
    dialog.accept()

    assert updated == [True]
    assert refreshed == []
    window.deleteLater()


def test_arc_sampling_only_change_rerenders_without_reexecution(qt_app, monkeypatch):
    window = MainWindow()
    dialog = window.optionsDlg
    dialog.load_values()
    window.execution_result = object()
    updated = []
    rerendered = []
    monkeypatch.setattr(window, "updateData", lambda: updated.append(True) or True)
    monkeypatch.setattr(window, "rerenderCurrentResult", lambda: rerendered.append(True) or True)
    monkeypatch.setattr(window, "saveSettings", lambda: None)

    dialog.ui.maximumCircularRadiusSpin.setValue(window.maximumCircularRadius + 1.0)
    dialog.accept()

    assert updated == []
    assert rerendered == [True]
    window.deleteLater()


def test_options_default_file_type_is_not_taken_from_current_editor_mode(qt_app, monkeypatch):
    window = MainWindow()
    window.defaultFileType = 1
    window.ui.fileTypeCombo.setCurrentIndex(0)
    dialog = window.optionsDlg
    dialog.load_values()
    assert dialog.ui.fileTypeCombo.currentIndex() == 1

    applied = []
    monkeypatch.setattr(window, "changeFileType", applied.append)
    monkeypatch.setattr(window, "saveSettings", lambda: None)
    monkeypatch.setattr(window, "refreshPlotView", lambda: None)
    dialog.accept()
    assert window.defaultFileType == 1
    assert window.ui.fileTypeCombo.currentIndex() == 1
    assert applied == [1]
    window.deleteLater()
