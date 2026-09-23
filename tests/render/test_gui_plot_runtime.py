"""GUI plot refresh, playback, and execution integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication

from app.gcode.kernel import execute
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


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

    monkeypatch.setattr("app.ui.windows.main_window_execution.execute", fake_execute)
    window.correctionEnabled = False
    window.analyzeEditorSource()
    assert captured[-1]["tools"] == {} and captured[-1]["milling_tools"] == {}
    window.correctionEnabled = True
    window.analyzeEditorSource()
    assert captured[-1]["tools"] == window.tools
    assert captured[-1]["tools"] is not window.tools
    assert captured[-1]["milling_tools"] == window.millingTools
    assert captured[-1]["milling_tools"] is not window.millingTools
    window.deleteLater()


@pytest.mark.parametrize("enabled", [False, True])
def test_ignore_block_skip_is_passed_to_kernel(qt_app, monkeypatch, enabled):
    window = MainWindow()
    captured = []
    expected = execute("")

    def fake_execute(*args, **kwargs):
        captured.append(kwargs)
        return expected

    monkeypatch.setattr("app.ui.windows.main_window_execution.execute", fake_execute)
    window.ignoreBlockSkip = enabled
    window.analyzeEditorSource()

    assert captured[-1]["skip_optional_blocks"] is enabled
    window.deleteLater()


def test_loaded_program_fits_view_once_after_geometry_is_built(qt_app, tmp_path):
    window = MainWindow()
    window.autoUpdateEnabled = False
    fitted = []
    window.fitToView = lambda: fitted.append(True)
    source = tmp_path / "fit-on-load.nc"
    source.write_text("G21 G17 G90\nG0 X10 Y20 Z5\nG1 X100 Y50 Z-10 F100\nM30\n", encoding="utf-8")

    window.loadFile(str(source))
    assert fitted == []
    assert window.execution_result is None
    assert getattr(window, "_plot_source_stale") is True

    # Manual calculation after a fast Open performs the one pending fit.
    assert window.updateData()
    assert fitted == [True]
    assert window.execution_result is not None

    # Ordinary recalculation must preserve the camera chosen by the user.
    assert window.updateData()
    assert fitted == [True]
    window.deleteLater()


def test_milling_auto_refresh_fits_new_large_path_once_and_preserves_later_camera(qt_app):
    window = MainWindow()
    window.autoUpdateEnabled = True
    window.latheMode = False
    window._view_mode = "3d"  # pylint: disable=protected-access
    view = window.ui.graphicsView
    view.setCameraPosition(distance=40.0)
    fits = []
    original_fit = window.fitToView

    def record_fit():
        fits.append(True)
        original_fit()

    window.fitToView = record_fit
    window.ui.editor.setText("G21 G17 G90\nG0 X0 Y0 Z0\nG1 X1000 Y500 Z-20 F100\nM30")
    assert window.autoUpdate()
    assert fits == [True]
    fitted_distance = float(view.opts["distance"])
    assert fitted_distance > 40.0

    window.ui.editor.setText("G21 G17 G90\nG0 X0 Y0 Z0\nG1 X1010 Y500 Z-20 F100\nM30")
    assert window.autoUpdate()
    assert fits == [True]
    assert float(view.opts["distance"]) == pytest.approx(fitted_distance)
    window.deleteLater()


def test_milling_auto_refresh_keeps_camera_for_small_new_path(qt_app):
    window = MainWindow()
    window.autoUpdateEnabled = True
    window.latheMode = False
    window._view_mode = "3d"  # pylint: disable=protected-access
    window.xPosMach = 0.0
    window.yPosMach = 0.0
    window.zPosMach = 0.0
    view = window.ui.graphicsView
    view.setCameraPosition(distance=1000.0)
    previous_center = view.opts["center"]
    window.ui.editor.setText("G21 G17 G90\nG0 X0 Y0 Z0\nG1 X10 Y5 Z-2 F100\nM30")
    assert window.autoUpdate()
    assert float(view.opts["distance"]) == pytest.approx(1000.0)
    assert view.opts["center"] == previous_center
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
    window._calculate_editor_source = lambda **_kwargs: (result, None, True)  # pylint: disable=protected-access

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


def test_play_from_completed_macro_trace_restarts_at_beginning(qt_app):
    source = """G90G0G54X-10.Y0M3S4500
G43Z50.H1M8
#1=0.5
WHILE[#1LE50.]DO1
#2=50.-#1
#3=SQRT[2500.-[#2*#2]]
G1Z-#1F20
X-#3F500
G2I#3
#1=#1+0.5
END1
G0Z50.M5
M30"""
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.editor.setText(source)
    assert window.updateData()
    assert window.ui.horizontalSlider.value() == window.ui.horizontalSlider.maximum()

    cursor_changes = QSignalSpy(window.ui.editor.cursorPositionChanged)
    late_iteration = 100
    window.ui.horizontalSlider.setValue(late_iteration)
    qt_app.processEvents()
    assert window.ui.horizontalSlider.value() == late_iteration
    assert len(cursor_changes) == 0

    window.ui.horizontalSlider.setValue(window.ui.horizontalSlider.maximum())

    window.ui.actionPlay.setChecked(True)
    window.play()

    assert window.ui.horizontalSlider.value() == 0
    assert window.timer.isActive()
    assert window.ui.actionPlay.isChecked()
    window.stop()
    window.deleteLater()
