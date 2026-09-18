"""Options dialog and persisted runtime settings."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.main_window import MainWindow
from app.ui.dialogs.options import OptionsDialog
from app.ui.windows.main_window_execution import playback_interval_ms, playback_speed_level


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
    assert dialog.ui.linearColorEdit.text() == "#0000ff"
    assert dialog.ui.toolColorEdit.text() == "#4d99ff"
    assert dialog.ui.stlColorEdit.text() == "#b0b0b0"
    assert not dialog.ui.backgroundGradientCheck.isChecked()
    assert not dialog.ui.stlWireframeCheck.isChecked()
    assert dialog.ui.axesCheck.isChecked()
    assert dialog.ui.gridStepSpin.value() == 0
    assert dialog.ui.playbackSpeedSlider.value() == 3
    monkeypatch.setattr("app.ui.dialogs.options.QColorDialog.getColor", lambda *args: QColor("#abcdef"))
    dialog.ui.arcColorButton.click()
    assert dialog.ui.arcColorEdit.text() == "#abcdef"
    window.deleteLater()


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
    dialog.ui.autoUpdateCheck.setChecked(False)
    dialog.ui.autoUpdateMaxSegmentsSpin.setValue(7500)
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
    assert window.autoUpdateEnabled is False
    assert window.autoUpdateMaxSegments == 7500
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


@pytest.mark.parametrize("changed_option", ["units", "correction", "tolerance"])
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
    else:
        dialog.ui.arcToleranceSpin.setValue(window.arcTolerance * 2.0)
    dialog.accept()

    assert updated == [True]
    assert refreshed == []
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
