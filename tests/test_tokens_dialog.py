from __future__ import annotations

import csv
from pathlib import Path

import pytest
from gcode_samples import TURNING_PARTIAL_TRACE
from PyQt6.QtCore import QItemSelectionModel, QPoint, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow

from app.gcode.exporter import (
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    PLOT_DATA_MODE,
    TURN_FULL_PROGRAM_MODE,
)
from app.gcode.kernel import execute
from app.gcode.trace_tools import RenderPoint
from app.main_window import MainWindow
from app.ui.dialogs import _TurningToolEditor
from app.ui.generated.main_ui import Ui_MainWindow
from app.ui.options import OptionsDialog
from app.ui.tokens import TABLE_HEADINGS, TABLE_WIDTHS, TokensDialog, rows_from_execution


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


def test_turning_tip_orientation_icons_are_visible_in_editor_and_table(qt_app):
    window = MainWindow()
    editor = _TurningToolEditor(window)
    assert editor.tipOrientation.count() == 9
    assert all(not editor.tipOrientation.itemIcon(index).isNull() for index in range(9))

    window.tools = {"T0101": {"type": "turning", "noseRadius": 0.4, "tipOrientation": 7}}
    window.turningToolsDlg.loadValues()
    orientation = window.turningToolsDlg.ui.toolTable.item(0, 0)
    assert orientation.text() == "P7"
    assert not orientation.icon().isNull()
    editor.deleteLater()
    window.deleteLater()


def test_rows_use_kernel_tokens_and_diagnostics():
    source = "G0 X1 Z2\nG999 X3"
    rows = rows_from_execution(source, execute(source))
    assert rows[0].values[2] == "G:0 X:1 Z:2"
    assert rows[0].status == "OK"
    assert rows[1].status == "ERROR"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[16]


def test_tokens_support_follows_kernel_diagnostics_and_keeps_fractional_g_distinct():
    source = "G54\nG0.6 X1"
    rows = rows_from_execution(source, execute(source))
    assert rows[0].values[15] == "OK"
    assert rows[0].values[12] == "G54"
    assert rows[1].values[7] == ""
    assert rows[1].values[15] == "UNSUPPORTED"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[16]

    milling = rows_from_execution("G85 X1 Z-2 R0 F100", execute("G85 X1 Z-2 R0 F100", language="fanuc_mill"))
    assert milling[0].values[11] == "G85"
    assert milling[0].values[15] == "OK"


def test_tokens_groups_macro_flow_and_multiple_g_codes_follow_kernel_program():
    source = "#1=1\nG21 G18 G90 G190 G97\nIF[#1 EQ 1] GOTO10\nN10 G0 X20 Z0\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_turn"))

    assert rows[0].values[14] == "assign"
    assert rows[1].values[8] == "G18"
    assert rows[1].values[9] == "G21"
    assert rows[1].values[12] == "G90,G190"
    assert rows[1].values[13] == "G97"
    assert rows[2].values[14] == "if_goto"
    assert all(row.values[15] == "OK" for row in rows)


def test_tokens_show_unverified_milling_diagnostics_without_own_support_table():
    source = "G90 G17\nG64\nM123\nG1 X10 Y0 F100\nM30"
    rows = rows_from_execution(source, execute(source, language="fanuc_mill"))

    assert rows[1].values[15] == "UNVERIFIED"
    assert "UNSUPPORTED_G_CODE" in rows[1].values[16]
    assert rows[2].values[15] == "UNVERIFIED"
    assert "UNSUPPORTED_M_CODE" in rows[2].values[16]
    assert rows[3].values[15] == "OK"


def test_tokens_preserve_fatal_diagnostics_on_their_source_lines():
    source = "G999\nGOTO999"
    rows = rows_from_execution(source, execute(source, language="fanuc_turn"))

    assert rows[0].values[15] == "UNVERIFIED"
    assert "UNSUPPORTED_G_CODE" in rows[0].values[16]
    assert rows[1].status == "ERROR"
    assert "FLOW_TARGET_MISSING" in rows[1].values[16]


def test_tokens_keep_partial_turning_execution_diagnostics_and_later_source_rows():
    rows = rows_from_execution(
        TURNING_PARTIAL_TRACE,
        execute(TURNING_PARTIAL_TRACE, language="fanuc_turn"),
    )

    assert rows[1].values[15] == "UNVERIFIED"
    assert rows[3].values[15] == "UNSUPPORTED"
    assert rows[4].values[15] == "OK"
    assert rows[5].values[15] == "OK"


def test_tokens_dialog_refreshes_live_source_and_does_not_change_it(qt_app):
    current = {"source": "G0 X1 Z2"}
    analyses = []

    def analyze():
        analyses.append(current["source"])
        return execute(current["source"])

    parent = QMainWindow()
    dialog = TokensDialog(parent, lambda: current["source"], analyze)
    dialog.show()
    qt_app.processEvents()
    assert analyses == ["G0 X1 Z2"]
    assert dialog.model.rowCount() == 1
    assert dialog.model.item(0, 17).text() == "Yes"

    current["source"] = "G0 X1\nG999 X2"
    dialog.refresh()
    assert analyses[-1] == current["source"]
    assert dialog.model.rowCount() == 2
    assert dialog.model.item(1, 17).text() == "No"
    assert dialog.model.item(0, 0).background().color().name() == "#e7f6e7"
    assert dialog.model.item(1, 0).background().color().name() == "#ffe6e6"
    assert dialog.model.item(0, 0).foreground().color().name() == "#111111"
    assert current["source"] == "G0 X1\nG999 X2"


def test_tokens_copy_export_and_reset_columns(qt_app, monkeypatch, tmp_path):
    source = "G0 X1\nG1 Z2"
    parent = QMainWindow()
    dialog = TokensDialog(parent, lambda: source, lambda: execute(source))
    dialog.refresh()
    selection = dialog.ui.tokenTable.selectionModel()
    for row in range(2):
        index = dialog.model.index(row, 0)
        selection.select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    dialog.copy_selected_rows()
    copied = QApplication.clipboard().text()
    assert copied.count("\n") == 1
    assert all(len(line.split("\t")) == len(TABLE_HEADINGS) for line in copied.splitlines())

    output = tmp_path / "tokens.csv"
    monkeypatch.setattr("app.ui.tokens.QFileDialog.getSaveFileName", lambda *args: (str(output), "CSV"))
    dialog.export_csv()
    with output.open(encoding="utf-8", newline="") as stream:
        exported = list(csv.reader(stream, delimiter=";"))
    assert tuple(exported[0]) == TABLE_HEADINGS
    assert exported[1] == [dialog.model.item(0, column).text() for column in range(dialog.model.columnCount())]

    dialog.ui.tokenTable.setColumnWidth(0, 200)
    dialog.ui.tokenTable.horizontalScrollBar().setValue(10)
    dialog.ui.tokenTable.verticalScrollBar().setValue(10)
    dialog.reset_columns()
    assert tuple(dialog.ui.tokenTable.columnWidth(column) for column in range(len(TABLE_WIDTHS))) == TABLE_WIDTHS
    assert dialog.ui.tokenTable.horizontalScrollBar().value() == 0
    assert dialog.ui.tokenTable.verticalScrollBar().value() == 0


def test_options_dialog_is_independent_and_language_change_is_locked(qt_app):
    parent = QMainWindow()
    dialog = OptionsDialog(parent)
    assert dialog.parent() is parent
    assert dialog.windowTitle() == "Options"
    assert dialog.ui.buttonBox.button(dialog.ui.buttonBox.StandardButton.RestoreDefaults) is not None
    assert dialog.ui.languageCombo.count() == 2
    assert dialog.ui.languageCombo.isEnabled() is False


def test_options_defaults_and_color_picker(qt_app, monkeypatch):
    window = MainWindow()
    dialog = window.optionsDlg
    dialog.ui.linearColorEdit.setText("#123456")
    dialog.restore_defaults()
    assert dialog.ui.autoUpdateCheck.isChecked()
    assert dialog.ui.autoUpdateMaxSegmentsSpin.value() == 20000
    assert dialog.ui.linearColorEdit.text() == "#0000ff"
    assert dialog.ui.axesCheck.isChecked()
    assert dialog.ui.gridStepSpin.value() == 0
    monkeypatch.setattr("app.ui.options.QColorDialog.getColor", lambda *args: QColor("#abcdef"))
    dialog.ui.arcColorButton.click()
    assert dialog.ui.arcColorEdit.text() == "#abcdef"
    window.deleteLater()


def test_options_apply_every_runtime_plot_control(qt_app, monkeypatch):
    window = MainWindow()
    dialog = window.optionsDlg
    saved = []
    refreshed = []
    monkeypatch.setattr(window, "saveSettings", lambda: saved.append(True))
    monkeypatch.setattr(window, "refreshPlotView", lambda: refreshed.append(True))
    dialog.load_values()
    dialog.ui.rapidColorEdit.setText("#110000")
    dialog.ui.linearColorEdit.setText("#001100")
    dialog.ui.arcColorEdit.setText("#000011")
    dialog.ui.currentColorEdit.setText("#111111")
    dialog.ui.backgroundColorEdit.setText("#eeeeee")
    dialog.ui.lineWidthSpin.setValue(2.5)
    dialog.ui.gridStepSpin.setValue(12.5)
    dialog.ui.axesCheck.setChecked(False)
    dialog.ui.gridCheck.setChecked(True)
    dialog.ui.arcToleranceSpin.setValue(0.02)
    dialog.ui.correctionCheck.setChecked(False)
    dialog.ui.autoUpdateCheck.setChecked(False)
    dialog.ui.autoUpdateMaxSegmentsSpin.setValue(7500)
    dialog.accept()
    assert (window.plotRapidColor, window.plotLineColor, window.plotArcColor, window.plotCurrentColor) == (
        "#110000",
        "#001100",
        "#000011",
        "#111111",
    )
    assert window.plotBackground == "#eeeeee"
    assert window.plotLineWidth == 2.5
    assert window.plotGridStep == 12.5
    assert window.plotAxes is False
    assert window.plotGrid is True and window.ui.actionGrid.isChecked()
    assert window.arcTolerance == 0.02
    assert window.correctionEnabled is False
    assert window.autoUpdateEnabled is False
    assert window.autoUpdateMaxSegments == 7500
    assert saved == [True] and refreshed == [True]
    window.deleteLater()


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
    window.ui.langCombo.setCurrentIndex(0)
    dialog = window.optionsDlg
    dialog.load_values()
    assert dialog.ui.fileTypeCombo.currentIndex() == 1

    applied = []
    monkeypatch.setattr(window, "changeLang", applied.append)
    monkeypatch.setattr(window, "saveSettings", lambda: None)
    monkeypatch.setattr(window, "refreshPlotView", lambda: None)
    dialog.accept()
    assert window.defaultFileType == 1
    assert window.ui.langCombo.currentIndex() == 1
    assert applied == [1]
    window.deleteLater()


def test_axes_grid_and_fixed_grid_step_change_rendered_items(qt_app):
    window = MainWindow()
    window.plotAxes = False
    window.plotGrid = False
    window.loadPlot()
    assert window.ui.graphicsView.items == []
    window.plotGrid = True
    window.plotGridStep = 25.0
    window.loadPlot()
    assert len(window.ui.graphicsView.items) == 1
    assert window.ui.graphicsView.items[0].spacing()[0] == 25.0
    window.plotAxes = True
    window.loadPlot()
    assert len(window.ui.graphicsView.items) == 2
    assert window._axis_triad_item in window.ui.graphicsView.items  # pylint: disable=protected-access
    window.deleteLater()


def test_arc_tolerance_controls_render_sampling(qt_app):
    window = MainWindow()
    result = execute("G17 G0 X0 Y0\nG2 X10 Y0 I5 J0", language="fanuc_mill")
    window.arcTolerance = 0.5
    coarse = window.arcPointsPerCircle(result)
    window.arcTolerance = 0.001
    fine = window.arcPointsPerCircle(result)
    assert fine > coarse >= 3
    window.deleteLater()


def test_correction_toggle_controls_tools_passed_to_kernel(qt_app, monkeypatch):
    window = MainWindow()
    captured = []
    expected = execute("")

    def fake_execute(*args, **kwargs):
        captured.append(kwargs)
        return expected

    monkeypatch.setattr("app.ui.main_window_execution.execute", fake_execute)
    window.correctionEnabled = False
    window.analyzeEditorSource()
    assert captured[-1]["tools"] == {} and captured[-1]["milling_tools"] == {}
    window.correctionEnabled = True
    window.analyzeEditorSource()
    assert captured[-1]["tools"] is window.tools
    assert captured[-1]["milling_tools"] is window.millingTools
    window.deleteLater()


def test_machine_specific_actions_follow_active_profile_without_restart(qt_app):
    window = MainWindow()

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    assert window.ui.actionTurningTools.isEnabled()
    assert not window.ui.actionMillingTools.isEnabled()
    assert window.ui.actionRelative_to_start.isEnabled()
    assert window.ui.actionAbsolute.isEnabled()
    assert window.ui.actionRadius_value.isEnabled()
    assert window.optionsDlg.ui.arcToleranceSpin.isEnabled()

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert not window.ui.actionTurningTools.isEnabled()
    assert window.ui.actionMillingTools.isEnabled()
    assert window.ui.actionRelative_to_start.isEnabled()
    assert window.ui.actionAbsolute.isEnabled()
    assert window.ui.actionRadius_value.isEnabled()
    assert window.optionsDlg.ui.arcToleranceSpin.isEnabled()
    window.deleteLater()


def test_machine_specific_actions_stay_synchronized_after_new_and_load(qt_app, tmp_path):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(True)
    window.newFile()
    assert window.ui.actionTurningTools.isEnabled()
    assert not window.ui.actionMillingTools.isEnabled()

    source = tmp_path / "sample.nc"
    source.write_text("G21 G18\nG0 X20 Z0\nM30\n", encoding="utf-8")
    window.loadFile(str(source))
    qt_app.processEvents()
    assert window.ui.actionTurningTools.isEnabled()
    assert not window.ui.actionMillingTools.isEnabled()
    window.deleteLater()


def test_auto_refresh_preserves_editor_cursor_position(qt_app):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G18\nG0 X20 Z0\nG1 X30 Z-5 F100\nM30")
    assert window.updateData()

    window.ui.editor.setCursorPosition(1, 2)
    QTest.keyClick(window.ui.editor, Qt.Key.Key_Space)
    expected_cursor = window.ui.editor.getCursorPosition()
    QTest.qWait(600)
    qt_app.processEvents()

    assert window.ui.editor.getCursorPosition() == expected_cursor
    assert window.execution_result is not None
    window.deleteLater()


def test_auto_refresh_replaces_plot_after_editor_change(qt_app):
    window = MainWindow()
    window.autoUpdateEnabled = True
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G18\nG0 X20 Z0\nG1 X30 Z-5 F100\nM30")
    assert window.updateData()
    old_result = window.execution_result
    old_endpoint = window.execution_result.motions[-1].end_x

    window.ui.editor.setCursorPosition(2, 5)
    QTest.keyClick(window.ui.editor, Qt.Key.Key_1)

    # Until the debounce expires, the slider and plot still describe the old
    # trajectory instead of being cleared by the document-modified signal.
    assert window.execution_result is old_result
    assert window.execution_result.motions[-1].end_x == old_endpoint

    QTest.qWait(600)
    qt_app.processEvents()

    assert window.execution_result is not old_result
    assert window.execution_result.motions[-1].end_x == pytest.approx(310.0)
    assert window.render_points[-1].x == pytest.approx(155.0)
    window.deleteLater()


def test_long_manual_update_reports_progress_and_then_hides_it(qt_app):
    window = MainWindow()
    window.autoUpdateMaxSegments = 1
    setattr(window, "_auto_update_deferred", True)
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G18\nG0 X20 Z0\nG1 X30 Z-5 F100\nM30")

    assert window.updateData()
    assert window.progressBar.isVisibleTo(window)
    assert window.progressBar.value() == 100

    QTest.qWait(600)
    qt_app.processEvents()
    assert window.progressBar.isHidden()
    window.deleteLater()


def test_arc_heavy_milling_file_exceeds_auto_update_segment_limit(qt_app):
    window = MainWindow()
    window.autoUpdateMaxSegments = 20000
    window.latheMode = False
    window.arcTolerance = 0.001
    window.correctionEnabled = False
    window.ui.actionLatheMode.setChecked(False)
    source = Path("tests/fixtures/milling/macro_boss_milling.nc").read_text(encoding="utf-8")
    window.ui.editor.setText(source)
    result = execute(source, language="fanuc_mill")
    assert result.motions
    window._execute_editor_source = lambda *, show_errors: result  # pylint: disable=protected-access

    window.autoUpdate()

    assert window.ui.editor.lines() < 100
    assert getattr(window, "_auto_update_deferred") is True
    assert "press Update" in window.ui.statusbar.currentMessage()
    window.deleteLater()


def test_stale_editor_source_does_not_drive_old_trajectory_slider(qt_app):
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G18\nG0 X20 Z0\nG1 X30 Z-5 F100\nM30")
    assert window.updateData()

    window.ui.horizontalSlider.setValue(1)
    window.ui.editor.setCursorPosition(1, 2)
    QTest.keyClick(window.ui.editor, Qt.Key.Key_Space)
    stale_slider_value = window.ui.horizontalSlider.value()
    window.ui.editor.setCursorPosition(2, 0)
    qt_app.processEvents()

    assert getattr(window, "_plot_source_stale") is True
    assert window.ui.horizontalSlider.value() == stale_slider_value
    window.deleteLater()


def test_vbo_playback_view_changes_and_reload_preserve_scene_contract(qt_app):
    window = MainWindow()
    window.latheMode = False
    window.arc_type = 1
    window.plotAxes = True
    window.ui.actionLatheMode.setChecked(False)
    window.ui.editor.setText("O1\nG0 X10 Y0 Z0\nG1 X20 Y5 F100\nG2 X30 Y5 I5 J0\nM30")
    assert window.updateData()
    assert window.execution_result.events

    item = window._toolpath_item  # pylint: disable=protected-access
    axis_item = window._axis_triad_item  # pylint: disable=protected-access
    assert axis_item.center == (0.0, 0.0, 0.0)
    vertices = item.packed_vertices
    assert item.logical_count == len(window.execution_result.motions)
    assert item in window.ui.graphicsView.items

    window.ui.horizontalSlider.setValue(1)
    first_visible = item.visible_segment_count
    window.forward()
    assert window.ui.horizontalSlider.value() == 2
    window.backward()
    assert window.ui.horizontalSlider.value() == 1
    window.ui.horizontalSlider.setValue(window.ui.horizontalSlider.maximum())
    assert item.visible_segment_count > first_visible
    window.ui.horizontalSlider.setValue(1)
    assert item.visible_segment_count == first_visible
    assert item.packed_vertices is vertices

    window.ui.editor.setCursorPosition(0, 0)
    cursor = window.ui.editor.getCursorPosition()
    first_visible_line = window.ui.editor.firstVisibleLine()
    window.viewTop()
    window.viewFront()
    window.viewLeft()
    window.view3d()
    assert window._toolpath_item is item  # pylint: disable=protected-access
    assert window._axis_triad_item is axis_item  # pylint: disable=protected-access
    assert axis_item.center == (0.0, 0.0, 0.0)
    assert item.packed_vertices is vertices
    assert item in window.ui.graphicsView.items
    assert window.ui.editor.getCursorPosition() == cursor
    assert window.ui.editor.firstVisibleLine() == first_visible_line

    window.ui.editor.setText("O2\nT1 M6\nG0 X1\nM30")
    assert window.updateData()
    assert window._toolpath_item is item  # pylint: disable=protected-access
    assert item.packed_vertices is not vertices
    assert any(event.kind == "tool_change" for event in window.execution_result.events)
    window.deleteLater()


def test_axis_triad_stays_at_coordinate_zero_when_switching_mill_to_lathe(qt_app):
    window = MainWindow()
    window.latheMode = False
    window.arc_type = 1
    window.plotAxes = True
    window.ui.actionLatheMode.setChecked(False)
    window.ui.editor.setText("G90 G0 X100 Y200 Z300\nG1 X200 Y300 Z400 F100\nM30")
    assert window.updateData()
    milling_view_center = window.ui.graphicsView.opts["center"]
    axis_item = window._axis_triad_item  # pylint: disable=protected-access
    assert axis_item.center == (0.0, 0.0, 0.0)

    window.ui.editor.setText("G18 G0 X20 Z10\nG1 X40 Z-30 F100\nM30")
    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()

    turning_view_center = window.ui.graphicsView.opts["center"]
    assert window.latheMode is True
    assert window._axis_triad_item is axis_item  # pylint: disable=protected-access
    assert axis_item.center == (0.0, 0.0, 0.0)
    assert (turning_view_center.x(), turning_view_center.y(), turning_view_center.z()) != pytest.approx(
        (milling_view_center.x(), milling_view_center.y(), milling_view_center.z())
    )
    window.deleteLater()


def test_export_dialog_has_four_logical_modes_and_separate_representation_options(qt_app):
    window = MainWindow()
    dialog = window.exportDlg

    assert dialog.ui.langCmbBox.count() == 4
    assert [dialog.ui.langCmbBox.itemText(index) for index in range(4)] == [
        "TURN FULL PROGRAM",
        "MILL FULL PROGRAM",
        "EXPANDED EXECUTION",
        "PLOT DATA",
    ]
    assert dialog.arcOutputCmbBox.count() == 4
    assert dialog.ui.incrCmbBox.itemText(0) == "G90 Absolute"
    assert dialog.ui.incrCmbBox.itemText(1) == "G91 Incremental"

    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()
    model = dialog.ui.langCmbBox.model()
    assert model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert not model.item(MILL_FULL_PROGRAM_MODE).isEnabled()

    dialog.ui.langCmbBox.setCurrentIndex(EXPANDED_EXECUTION_MODE)
    assert dialog.arcOutputCmbBox.isEnabled()
    assert dialog.ui.incrCmbBox.isEnabled()
    dialog.ui.langCmbBox.setCurrentIndex(PLOT_DATA_MODE)
    assert not dialog.arcOutputCmbBox.isEnabled()
    assert not dialog.ui.incrCmbBox.isEnabled()

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()
    assert not model.item(TURN_FULL_PROGRAM_MODE).isEnabled()
    assert model.item(MILL_FULL_PROGRAM_MODE).isEnabled()
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


def test_fit_to_view_keeps_turning_fit_behavior(qt_app):
    window = MainWindow()
    window.latheMode = True
    window._view_mode = "lathe"  # pylint: disable=protected-access
    window.render_points = [
        RenderPoint(-20, -10, -30, None, 0, 0),
        RenderPoint(40, 50, 70, None, 1, 1),
    ]
    window.ui.graphicsView.opts["center"] = window.ui.graphicsView.opts["center"] * 0
    window.ui.graphicsView.opts["distance"] = 1.0
    window.ui.graphicsView.opts["fov"] = 0.01
    window.ui.actionFitToView.trigger()
    center = window.ui.graphicsView.opts["center"]
    assert (center.x(), center.y(), center.z()) == pytest.approx((10.0, 20.0, 20.0))
    assert window.ui.graphicsView.opts["distance"] > 1.0
    assert not window.ui.actionFitToView.icon().isNull()
    window.deleteLater()


@pytest.mark.parametrize(
    ("view_mode", "fov", "elevation", "azimuth"),
    [
        ("3d", 60.0, 30.0, -45.0),
        ("top", 0.01, 90.0, -90.0),
        ("front", 0.01, 0.0, -90.0),
        ("left", 0.01, 0.0, 180.0),
    ],
)
def test_milling_fit_keeps_every_bounds_corner_inside_view(qt_app, view_mode, fov, elevation, azimuth):
    window = MainWindow()
    window.latheMode = False
    window._view_mode = view_mode  # pylint: disable=protected-access
    window.ui.graphicsView.resize(800, 400)
    window.ui.graphicsView.opts["fov"] = fov
    window.ui.graphicsView.setCameraPosition(distance=1.0, elevation=elevation, azimuth=azimuth)
    bounds = ((-20.0, 40.0), (-10.0, 50.0), (-30.0, 70.0))
    window.render_points = [
        RenderPoint(bounds[0][0], bounds[1][0], bounds[2][0], None, 0, 0),
        RenderPoint(bounds[0][1], bounds[1][1], bounds[2][1], None, 1, 1),
    ]

    window.fitToView()

    width = window.ui.graphicsView.width()
    height = window.ui.graphicsView.height()
    for x in bounds[0]:
        for y in bounds[1]:
            for z in bounds[2]:
                screen = window._project_world_to_screen(x, y, z)  # pylint: disable=protected-access
                assert screen is not None
                assert 0.04 * width <= screen[0] <= 0.96 * width
                assert 0.04 * height <= screen[1] <= 0.96 * height
    window.deleteLater()


def test_plot_context_menu_starts_with_fit_to_view(qt_app, monkeypatch):
    captured = []

    class Menu:
        def addAction(self, action):
            captured.append(action)

        def addSeparator(self):
            captured.append(None)

        def exec(self, _point):
            return None

    window = MainWindow()
    monkeypatch.setattr("app.ui.main_window_plot.QMenu", Menu)
    window.plotContextMenu(QPoint())
    assert captured[0] is window.ui.actionFitToView
    window.deleteLater()
