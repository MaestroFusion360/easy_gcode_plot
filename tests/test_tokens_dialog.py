from __future__ import annotations

import csv

import pytest
from PyQt6.QtCore import QItemSelectionModel, QPoint
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QMainWindow

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
    assert len(window.ui.graphicsView.items) == 4
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
