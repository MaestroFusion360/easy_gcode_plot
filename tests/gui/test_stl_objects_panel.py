"""Behavioral tests for the standalone STL scene-object dock."""

# pylint: disable=protected-access

from __future__ import annotations

import random

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractButton, QApplication, QMainWindow, QWidget

from app.ui.panels.stl_objects_panel import StlObjectsPanel
from app.ui.plot.stl_transform import MeshMeasurements


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qt_app):
    widget = StlObjectsPanel()
    yield widget
    widget.deleteLater()
    qt_app.processEvents()


def _record(signal):
    calls = []
    signal.connect(lambda *args: calls.append(args))
    return calls


def _assert_object_controls(panel, enabled):
    assert panel.deleteButton.isEnabled() is enabled
    assert panel.statisticsButton.isEnabled() is enabled
    assert all(
        panel.operationStack.widget(index).isEnabled() is enabled for index in range(panel.operationStack.count())
    )


def test_panel_starts_without_object_selection(panel):
    assert panel.objectList.count() == 0
    assert panel.objectList.currentRow() == -1
    assert panel.operationCombo.count() == 6
    assert panel.operationStack.count() == 6
    assert panel.operationCombo.currentIndex() == panel.operationStack.currentIndex() == 0
    _assert_object_controls(panel, False)


def _shown_dock(qt_app):
    window = QMainWindow()
    window.setCentralWidget(QWidget())
    window.resize(900, 600)
    dock = StlObjectsPanel(window)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    window.show()
    qt_app.processEvents()
    return window, dock


def test_dock_is_fixed_without_float_or_close_buttons(qt_app):
    window, dock = _shown_dock(qt_app)
    try:
        assert dock.features() == dock.DockWidgetFeature.NoDockWidgetFeatures
        assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
        assert not dock.isFloating()

        for button_name in ("qt_dockwidget_floatbutton", "qt_dockwidget_closebutton"):
            button = dock.findChild(QAbstractButton, button_name)
            assert button is None or not button.isVisible()

        dock.hide()
        assert not dock.isVisible()
        dock.show()
        assert dock.isVisible()
        assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
        assert not dock.isFloating()
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_dock_width_can_shrink_below_content_size_hint(qt_app):
    window, dock = _shown_dock(qt_app)
    try:
        assert dock.widget().minimumSizeHint().width() > 120
        assert dock.minimumSizeHint().width() == 0
        window.resizeDocks([dock], [120], Qt.Orientation.Horizontal)
        qt_app.processEvents()
        assert dock.width() <= 150
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_set_objects_populates_names_clamps_selection_and_does_not_emit_selection(panel):
    calls = _record(panel.selectionChanged)

    panel.set_objects(["first.stl", "second.stl", "third.stl"], current_row=99)
    assert [panel.objectList.item(index).text() for index in range(panel.objectList.count())] == [
        "first.stl",
        "second.stl",
        "third.stl",
    ]
    assert panel.objectList.currentRow() == 2
    assert calls == []
    _assert_object_controls(panel, True)

    panel.set_objects(["only.stl"], current_row=-20)
    assert panel.objectList.currentRow() == 0
    assert calls == []


def test_empty_object_list_clears_selection_and_disables_object_controls(panel):
    panel.set_objects(["part.stl"], current_row=0)
    _assert_object_controls(panel, True)

    panel.set_objects([], current_row=0)

    assert panel.objectList.count() == 0
    assert panel.objectList.currentRow() == -1
    _assert_object_controls(panel, False)


def test_user_selection_emits_row_and_updates_enabled_state(panel):
    panel.set_objects(["a.stl", "b.stl"], current_row=0)
    calls = _record(panel.selectionChanged)

    panel.objectList.setCurrentRow(1)
    assert calls == [(1,)]
    _assert_object_controls(panel, True)

    panel.objectList.setCurrentRow(-1)
    assert calls == [(1,), (-1,)]
    _assert_object_controls(panel, False)


def test_operation_combo_tracks_stacked_page(panel):
    for index in range(panel.operationCombo.count()):
        panel.operationCombo.setCurrentIndex(index)
        assert panel.operationStack.currentIndex() == index


def test_history_buttons_follow_explicit_availability(panel):
    panel.set_history_available(undo=False, redo=False)
    assert not panel.undoButton.isEnabled()
    assert not panel.redoButton.isEnabled()

    panel.set_history_available(undo=True, redo=False)
    assert panel.undoButton.isEnabled()
    assert not panel.redoButton.isEnabled()

    panel.set_history_available(undo=False, redo=True)
    assert not panel.undoButton.isEnabled()
    assert panel.redoButton.isEnabled()


def test_action_buttons_emit_undo_redo_statistics_and_delete(panel):
    panel.set_objects(["part.stl"], current_row=0)
    panel.set_history_available(undo=True, redo=True)
    undo = _record(panel.undoRequested)
    redo = _record(panel.redoRequested)
    statistics = _record(panel.statisticsRequested)
    delete = _record(panel.deleteRequested)

    panel.undoButton.click()
    panel.redoButton.click()
    panel.statisticsButton.click()
    panel.deleteButton.click()

    assert undo == [()]
    assert redo == [()]
    assert statistics == [()]
    assert delete == [()]


def test_pivot_modes_update_editor_state_and_emit_automatic_modes(panel):
    panel.set_objects(["part.stl"], current_row=0)
    calls = _record(panel.pivotRequested)

    custom_index = panel.pivotMode.findData("custom")
    center_index = panel.pivotMode.findData("center")
    min_index = panel.pivotMode.findData("min")
    origin_index = panel.pivotMode.findData("origin")

    panel.pivotMode.setCurrentIndex(custom_index)
    assert all(not widget.isReadOnly() for widget in (panel.pivotX, panel.pivotY, panel.pivotZ))
    assert not panel.pivotApplyButton.isHidden()
    assert calls == []

    for index, mode in ((center_index, "center"), (min_index, "min"), (origin_index, "origin")):
        panel.pivotMode.setCurrentIndex(index)
        assert all(widget.isReadOnly() for widget in (panel.pivotX, panel.pivotY, panel.pivotZ))
        assert panel.pivotApplyButton.isHidden()
        assert calls[-1] == (mode, None)


def test_pivot_mode_change_without_selection_does_not_request_transform(panel):
    panel.set_objects([], current_row=-1)
    calls = _record(panel.pivotRequested)

    panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("custom"))
    panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("origin"))

    assert calls == []


def test_custom_pivot_apply_emits_exact_coordinates(panel):
    panel.set_objects(["part.stl"], current_row=0)
    panel.pivotMode.setCurrentIndex(panel.pivotMode.findData("custom"))
    panel.pivotX.setValue(1.25)
    panel.pivotY.setValue(-2.5)
    panel.pivotZ.setValue(30.125)
    calls = _record(panel.pivotRequested)

    panel.pivotApplyButton.click()

    assert calls == [("custom", (1.25, -2.5, 30.125))]


def test_set_object_state_is_silent_and_updates_source_and_world_pivots(panel):
    panel.set_objects(["part.stl"], current_row=0)
    calls = _record(panel.pivotRequested)

    panel.set_object_state(pivot_mode="custom", pivot=(1.0, 2.0, 3.0), world_pivot=(10.0, 20.0, 30.0))

    assert panel.pivotMode.currentData() == "custom"
    assert tuple(widget.value() for widget in (panel.pivotX, panel.pivotY, panel.pivotZ)) == (1.0, 2.0, 3.0)
    assert tuple(widget.value() for widget in (panel.positionX, panel.positionY, panel.positionZ)) == (
        10.0,
        20.0,
        30.0,
    )
    assert all(not widget.isReadOnly() for widget in (panel.pivotX, panel.pivotY, panel.pivotZ))
    assert calls == []


def test_move_rotate_mirror_and_scale_emit_current_values(panel):
    panel.set_objects(["part.stl"], current_row=0)
    move = _record(panel.moveRequested)
    rotate = _record(panel.rotateRequested)
    mirror = _record(panel.mirrorRequested)
    scale = _record(panel.scaleRequested)

    for widget, value in zip((panel.positionX, panel.positionY, panel.positionZ), (12.5, -7.25, 100.0)):
        widget.setValue(value)
    panel.moveButton.click()

    panel.rotateAxis.setCurrentText("Y")
    panel.rotateAngle.setValue(-123.5)
    panel.rotateButton.click()

    panel.mirrorPlane.setCurrentText("Z")
    panel.mirrorButton.click()

    panel.scaleFactor.setValue(25.4)
    panel.scaleButton.click()

    assert move == [((12.5, -7.25, 100.0),)]
    assert rotate == [("Y", -123.5)]
    assert mirror == [("Z",)]
    assert scale == [(25.4,)]


def test_circular_array_emits_complete_operation_specification(panel):
    panel.set_objects(["part.stl"], current_row=0)
    calls = _record(panel.circularArrayRequested)
    panel.circularCount.setValue(7)
    panel.circularAngle.setValue(-270.0)
    panel.circularAxis.setCurrentText("X")
    for widget, value in zip((panel.circularX, panel.circularY, panel.circularZ), (5.0, -6.0, 7.5)):
        widget.setValue(value)
    panel.rotateCopies.setChecked(False)

    panel.circularButton.click()

    assert calls == [(7, -270.0, "X", (5.0, -6.0, 7.5), False)]


def test_rectangular_array_emits_counts_before_steps(panel):
    panel.set_objects(["part.stl"], current_row=0)
    calls = _record(panel.rectangularArrayRequested)
    for widget, value in zip(panel.rectCounts, (2, 3, 4)):
        widget.setValue(value)
    for widget, value in zip(panel.rectSteps, (10.0, -20.0, 30.5)):
        widget.setValue(value)

    panel.rectangularButton.click()

    assert calls == [(2, 3, 4, 10.0, -20.0, 30.5)]


def test_section_emits_axis_offset_and_selected_side(panel):
    panel.set_objects(["part.stl"], current_row=0)
    section = _record(panel.sectionRequested)
    clear = _record(panel.clearSectionRequested)

    panel.sectionAxis.setCurrentText("Y")
    panel.sectionOffset.setValue(42.25)
    panel.sectionKeepSide.setCurrentIndex(1)
    panel.sectionButton.click()
    panel.clearSectionButton.click()

    assert section == [("Y", 42.25, False)]
    assert clear == [()]


def test_section_offset_recenters_for_each_axis_from_mesh_bounds(panel):
    measurement = MeshMeasurements(
        area=1.0,
        volume=1.0,
        center_of_mass=(0.0, 0.0, 0.0),
        bounds=((-10.0, 30.0), (5.0, 15.0), (-100.0, 20.0)),
    )

    panel.set_mesh_bounds(measurement)
    assert panel.sectionAxis.currentText() == "X"
    assert panel.sectionOffset.value() == pytest.approx(10.0)

    panel.sectionAxis.setCurrentText("Y")
    assert panel.sectionOffset.value() == pytest.approx(10.0)

    panel.sectionAxis.setCurrentText("Z")
    assert panel.sectionOffset.value() == pytest.approx(-40.0)


def test_clearing_mesh_bounds_stops_automatic_section_recentering(panel):
    measurement = MeshMeasurements(
        area=1.0,
        volume=1.0,
        center_of_mass=(0.0, 0.0, 0.0),
        bounds=((0.0, 10.0), (20.0, 40.0), (100.0, 200.0)),
    )
    panel.set_mesh_bounds(measurement)
    panel.set_mesh_bounds(None)
    panel.sectionOffset.setValue(123.0)

    panel.sectionAxis.setCurrentText("Y")

    assert panel.sectionOffset.value() == pytest.approx(123.0)


def test_set_measurements_keeps_compatibility_state_and_bounds(panel):
    measurement = MeshMeasurements(
        area=50.0,
        volume=100.0,
        center_of_mass=(1.0, 2.0, 3.0),
        bounds=((2.0, 6.0), (10.0, 14.0), (-4.0, 8.0)),
    )

    panel.set_measurements(measurement)

    assert panel._measurements is measurement
    assert panel._section_bounds == measurement.bounds
    assert panel.sectionOffset.value() == pytest.approx(4.0)


def test_format_measurements_formats_closed_mesh_in_mm_and_inches():
    measurement = MeshMeasurements(
        area=645.16,
        volume=25.4**3,
        center_of_mass=(25.4, 50.8, 76.2),
        bounds=((0.0, 25.4), (-25.4, 25.4), (50.8, 76.2)),
    )

    metric = StlObjectsPanel.format_measurements(measurement, inches=False)
    imperial = StlObjectsPanel.format_measurements(measurement, inches=True)

    assert "645.160 mm²" in metric
    assert f"{25.4**3:.3f} mm³" in metric
    assert "25.400, 50.800, 76.200 mm" in metric
    assert "Xmin = 0.000 mm; Xmax = 25.400 mm; Length = 25.400 mm" in metric
    assert "1.000 in²" in imperial
    assert "1.000 in³" in imperial
    assert "1.000, 2.000, 3.000 in" in imperial
    assert "Ymin = -1.000 in; Ymax = 1.000 in; Length = 2.000 in" in imperial


def test_format_measurements_marks_open_mesh_solid_properties_undefined():
    measurement = MeshMeasurements(
        area=12.5,
        volume=None,
        center_of_mass=None,
        bounds=((0.0, 1.0), (0.0, 2.0), (0.0, 3.0)),
    )

    text = StlObjectsPanel.format_measurements(measurement)

    assert "12.500 mm²" in text
    assert text.count("undefined (open mesh)") == 2


def test_numeric_controls_keep_safety_ranges_and_non_tracking_input(panel):
    double_spins = (
        panel.pivotX,
        panel.pivotY,
        panel.pivotZ,
        panel.positionX,
        panel.positionY,
        panel.positionZ,
        panel.rotateAngle,
        panel.scaleFactor,
        panel.circularAngle,
        panel.circularX,
        panel.circularY,
        panel.circularZ,
        *panel.rectSteps,
        panel.sectionOffset,
    )
    assert all(not widget.keyboardTracking() for widget in double_spins)
    assert panel.rotateAngle.minimum() == -360_000
    assert panel.rotateAngle.maximum() == 360_000
    assert panel.scaleFactor.minimum() > 0.0
    assert panel.scaleFactor.value() == pytest.approx(1.0)
    assert panel.circularCount.minimum() == 1
    assert panel.circularCount.maximum() == 10_000
    assert all(widget.minimum() == 1 and widget.maximum() == 10_000 for widget in panel.rectCounts)


def test_disabled_object_actions_do_not_emit_when_no_selection(panel):
    panel.set_objects([], current_row=-1)
    delete = _record(panel.deleteRequested)
    statistics = _record(panel.statisticsRequested)
    move = _record(panel.moveRequested)

    panel.deleteButton.click()
    panel.statisticsButton.click()
    panel.moveButton.click()

    assert delete == []
    assert statistics == []
    assert move == []


def test_deterministic_monkey_sequence_preserves_panel_invariants(panel):
    """Exercise many repeatable GUI state transitions without relying on screen coordinates."""
    rng = random.Random(169)
    panel.set_objects(["a.stl", "b.stl", "c.stl"], current_row=0)
    panel.set_history_available(undo=True, redo=True)

    clickable = (
        panel.undoButton,
        panel.redoButton,
        panel.statisticsButton,
        panel.deleteButton,
        panel.pivotApplyButton,
        panel.moveButton,
        panel.rotateButton,
        panel.mirrorButton,
        panel.scaleButton,
        panel.circularButton,
        panel.rectangularButton,
        panel.sectionButton,
        panel.clearSectionButton,
    )
    numeric = (
        panel.pivotX,
        panel.pivotY,
        panel.pivotZ,
        panel.positionX,
        panel.positionY,
        panel.positionZ,
        panel.rotateAngle,
        panel.scaleFactor,
        panel.circularAngle,
        panel.circularX,
        panel.circularY,
        panel.circularZ,
        *panel.rectSteps,
        panel.sectionOffset,
    )

    for _step in range(400):
        action = rng.randrange(8)
        if action == 0:
            panel.objectList.setCurrentRow(rng.choice((-1, 0, 1, 2)))
        elif action == 1:
            panel.operationCombo.setCurrentIndex(rng.randrange(panel.operationCombo.count()))
        elif action == 2:
            panel.pivotMode.setCurrentIndex(rng.randrange(panel.pivotMode.count()))
        elif action == 3:
            widget = rng.choice(numeric)
            low, high = widget.minimum(), widget.maximum()
            widget.setValue(low + (high - low) * rng.random())
        elif action == 4:
            rng.choice(clickable).click()
        elif action == 5:
            panel.rotateAxis.setCurrentIndex(rng.randrange(3))
            panel.mirrorPlane.setCurrentIndex(rng.randrange(3))
            panel.circularAxis.setCurrentIndex(rng.randrange(3))
            panel.sectionAxis.setCurrentIndex(rng.randrange(3))
        elif action == 6:
            panel.rotateCopies.setChecked(bool(rng.getrandbits(1)))
            panel.sectionKeepSide.setCurrentIndex(rng.randrange(2))
        else:
            panel.set_history_available(undo=bool(rng.getrandbits(1)), redo=bool(rng.getrandbits(1)))

        assert panel.operationStack.currentIndex() == panel.operationCombo.currentIndex()
        row = panel.objectList.currentRow()
        assert row in {-1, 0, 1, 2}
        expected_enabled = row >= 0
        _assert_object_controls(panel, expected_enabled)
        assert all(widget.minimum() <= widget.value() <= widget.maximum() for widget in numeric)
