"""Geometry picks and real Qt ruler interactions without editor side effects."""

# pylint: disable=protected-access

import math
from time import monotonic

import numpy as np
import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMatrix4x4, QMouseEvent, QVector3D
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QDialogButtonBox, QLabel, QLineEdit
from pyqtgraph.opengl import GLGridItem

from app.main_window import MainWindow
from app.ui.plot.geometry_picking import cursor_ray, pick_grid, pick_segments, pick_triangles, project_points
from app.ui.plot.stl import mesh_from_triangles


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    owner = MainWindow()
    owner.autoUpdateEnabled = False
    owner.ui.actionLatheMode.setChecked(False)
    owner.resize(1100, 750)
    owner.show()
    qt_app.processEvents()
    yield owner
    owner.ui.editor.setModified(False)
    owner.close()
    owner.deleteLater()
    qt_app.processEvents()


def test_segment_pick_uses_world_coordinates_and_snaps_endpoints():
    matrix = QMatrix4x4()
    matrix.ortho(-100, 100, -100, 100, -100, 100)
    segments = np.array([[(10, 20, 4), (50, 20, 4)]])
    viewport = (0, 0, 1000, 1000)
    hit = pick_segments((650, 400), segments, matrix, viewport)
    assert hit.point == pytest.approx((30, 20, 4))
    hit = pick_segments((748, 402), segments, matrix, viewport)
    assert hit.point == pytest.approx((50, 20, 4))
    assert pick_segments((650, 440), segments, matrix, viewport) is None


def test_perspective_segment_pick_stays_on_the_cursor_ray():
    matrix = QMatrix4x4()
    matrix.perspective(60, 1, 1, 100)
    viewport = (0, 0, 1000, 1000)
    segments = np.array([[(-2, 0, -5), (4, 0, -20)]])
    screen = project_points(segments[0], matrix, viewport)
    pixel = (screen[0, :2] + screen[1, :2]) / 2
    hit = pick_segments(pixel, segments, matrix, viewport)
    assert project_points([hit.point], matrix, viewport)[0, :2] == pytest.approx(pixel)
    origin, direction = cursor_ray(pixel, matrix, viewport)
    assert np.linalg.norm(np.cross(np.asarray(hit.point) - origin, direction)) < 1e-6


def test_facet_picking_chooses_front_surface_and_rejects_outside():
    matrix = QMatrix4x4()
    matrix.ortho(-10, 10, -10, 10, -10, 10)
    triangles = np.array([[(-5, -5, -3), (5, -5, -3), (0, 5, -3)], [(-5, -5, 3), (5, -5, 3), (0, 5, 3)]])
    hit = pick_triangles((500, 500), triangles, matrix, (0, 0, 1000, 1000))
    assert hit.point == pytest.approx((0, 0, 3))
    assert pick_triangles((950, 950), triangles, matrix, (0, 0, 1000, 1000)) is None


def test_grid_snap_uses_drawn_half_step_offset_and_rejects_distant_or_outside_nodes(qt_app):
    matrix = QMatrix4x4()
    matrix.ortho(-50, 50, -50, 50, -100, 100)
    grid = GLGridItem()
    grid.setSize(50, 50)
    grid.setSpacing(10, 10)
    grid.translate(10, 20, 0)
    viewport = (0, 0, 1000, 1000)
    hit = pick_grid((552, 152), grid, matrix, viewport)
    assert hit.point == pytest.approx((5, 35, 0))
    assert pick_grid((500, 500), grid, matrix, viewport) is None
    assert pick_grid((950, 150), grid, matrix, viewport) is None


def _grid_node(grid, offset=0):
    step = grid.spacing()[0]
    size = grid.size()[0]
    local = -size / 2 + (math.floor(size / (2 * step)) + offset) * step
    point = grid.transform().map(QVector3D(local, local, 0))
    return point.x(), point.y(), point.z()


@pytest.mark.parametrize("mode", ["top", "front", "left", "lathe"])
def test_measure_grid_snap_follows_view_step_and_visibility(window, qt_app, mode):
    if mode == "lathe":
        window.ui.actionLatheMode.setChecked(True)
    else:
        getattr(window, {"top": "viewTop", "front": "viewFront", "left": "viewLeft"}[mode])()
    window.ui.actionGrid.setChecked(True)
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    window._update_adaptive_grid()
    grid = window._lathe_grid_item if mode == "lathe" else window._milling_grid_item
    first, second = _grid_node(grid), _grid_node(grid, 1)
    pixel = window._project_world_to_screen(*first)
    assert ruler.pick(QPointF(pixel[0] + 2, pixel[1] + 2)) == pytest.approx(first, abs=1e-5)
    ruler.click(QPointF(*pixel))
    assert ruler.first == pytest.approx(first, abs=1e-5)
    ruler._hover = QPointF(*window._project_world_to_screen(*second))
    ruler._preview()
    assert ruler.second == pytest.approx(second, abs=1e-5) and not ruler.fixed
    ruler.click(ruler._hover)
    assert ruler.fixed
    ruler.ui.inchesCheck.setChecked(True)
    assert ruler.first == pytest.approx(first, abs=1e-5)
    window.plotGridStep = grid.spacing()[0] / 2
    window._update_adaptive_grid()
    manual_node = _grid_node(grid, 1)
    assert ruler.pick(QPointF(*window._project_world_to_screen(*manual_node))) == pytest.approx(manual_node, abs=1e-5)
    grid.setVisible(False)
    assert ruler.pick(QPointF(*window._project_world_to_screen(*manual_node))) is None
    grid.setVisible(True)
    window.ui.actionGrid.setChecked(False)
    assert ruler.pick(QPointF(*window._project_world_to_screen(*manual_node))) is None


def _screen(window, point):
    x, y = window._project_world_to_screen(*point)
    return QPoint(round(x), round(y))


@pytest.mark.parametrize("mode, axes", [("top", (0, 1)), ("front", (0, 2)), ("left", (1, 2))])
def test_ruler_two_clicks_live_preview_reset_and_editor_isolation(window, qt_app, mode, axes):
    window.ui.editor.setText("G21 G90 G17\nT1 M6\nG0 X0 Y0 Z0\nG1 X40 Y20 F100\nG1 X55 Y30 Z20\nM30")
    assert window.updateData()
    getattr(window, {"top": "viewTop", "front": "viewFront", "left": "viewLeft"}[mode])()
    window.ui.editor.setSelection(0, 0, 0, 3)
    selection = window.ui.editor.getSelection()
    caret = window.ui.editor.getCursorPosition()
    slider = window.ui.horizontalSlider.value()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    assert ruler.active and ruler.dialog.isVisible() and not ruler.dialog.isModal()
    first, second = (40, 20, 0), (55, 30, 20)
    QTest.mouseClick(window.ui.graphicsView, Qt.MouseButton.LeftButton, pos=_screen(window, first))
    assert ruler.first == pytest.approx(first)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(_screen(window, second)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(window.ui.graphicsView, event)
    deadline = monotonic() + 2
    while ruler.second is None:
        QTest.qWait(10)
        assert monotonic() < deadline, "The mouse-move event did not publish a live ruler preview"
    assert ruler.second == pytest.approx(second) and not ruler.fixed
    QTest.mouseClick(window.ui.graphicsView, Qt.MouseButton.LeftButton, pos=_screen(window, second))
    assert ruler.fixed and ruler.second == pytest.approx(second)
    delta = np.asarray(second) - first
    distance = math.hypot(*(delta[i] for i in axes))
    assert f"{distance:.3f}" in ruler.ui.statusLabel.text()
    assert window.ui.editor.getSelection() == selection
    assert window.ui.editor.getCursorPosition() == caret
    assert window.ui.horizontalSlider.value() == slider
    QTest.mouseClick(window.ui.graphicsView, Qt.MouseButton.LeftButton, pos=_screen(window, first))
    assert not ruler.fixed and ruler.second is None
    QTest.keyClick(window.ui.graphicsView, Qt.Key.Key_Escape)
    assert ruler.first is None
    window.view3d()
    assert not ruler.action.isEnabled() and not ruler.dialog.isVisible()


def test_lathe_measurement_distinguishes_diameter_coordinates_from_distance(window, qt_app):
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.setText("G21 G90\nT0101\nG0 X20 Z0\nG1 X30 Z12 F100\nM30")
    assert window.updateData()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    ruler.click(QPointF(_screen(window, (10, 0, 0))))
    ruler.click(QPointF(_screen(window, (15, 0, 12))))
    assert ruler.first == pytest.approx((10, 0, 0))
    assert ruler.second == pytest.approx((15, 0, 12))
    ruler.update_result()
    assert ruler.ui.coordinatesTable.item(0, 0).text() == "20.000"
    assert ruler.ui.coordinatesTable.item(1, 0).text() == "30.000"
    assert "13.000 mm" in ruler.ui.statusLabel.text()
    ruler.ui.inchesCheck.setChecked(True)
    assert f"{13 / 25.4:.3f} in" in ruler.ui.statusLabel.text()
    assert ruler.ui.coordinatesTable.item(0, 0).text() == f"{20 / 25.4:.3f}"


def test_stock_mesh_action_tracks_simulation_availability(window):
    window.ui.actionSaveStockStl.setEnabled(True)
    assert window.ui.actionInsertStockMesh.isEnabled()
    window.ui.actionSaveStockStl.setEnabled(False)
    assert not window.ui.actionInsertStockMesh.isEnabled()


def test_measure_dialog_has_one_status_label_and_no_caption_close_button(window):
    window.viewTop()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    assert ruler.dialog.findChildren(QLabel) == [ruler.ui.statusLabel]
    assert not ruler.dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint
    assert ruler.ui.inchesCheck.text() == "Inches"
    assert ruler.ui.coordinatesTable.editTriggers() == QAbstractItemView.EditTrigger.DoubleClicked


def test_measure_footer_positions_and_height_stay_stable(window, qt_app):
    window.viewTop()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    ui = ruler.ui
    qt_app.processEvents()
    reset = ui.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
    close = ui.buttonBox.button(QDialogButtonBox.StandardButton.Close)
    assert ui.statusLabel.geometry().bottom() < ui.inchesCheck.geometry().top()
    assert ui.inchesCheck.geometry().right() < ui.buttonBox.geometry().left()
    assert reset.geometry().right() < close.geometry().left()
    assert close.geometry().left() - reset.geometry().right() <= 16
    assert ui.statusLabel.height() >= ui.statusLabel.fontMetrics().lineSpacing() * 5
    size = ruler.dialog.size()
    ruler.first, ruler.second, ruler.fixed = (
        (-12345.678, 23456.789, -34567.89),
        (45678.901, -56789.012, 67890.123),
        True,
    )
    ruler.update_result()
    qt_app.processEvents()
    assert ruler.dialog.size() == size
    ui.inchesCheck.setChecked(True)
    qt_app.processEvents()
    assert ruler.dialog.size() == size
    ruler.reset()
    qt_app.processEvents()
    assert ruler.dialog.size() == size


def test_inches_toggle_preserves_physical_points_and_application_units(window):
    window.viewTop()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    ruler.first, ruler.second, ruler.fixed = (25.4, 0, 0), (50.8, 25.4, 0), True
    ruler.update_result()
    original = ruler.first, ruler.second
    ruler.ui.inchesCheck.setChecked(True)
    assert ruler.ui.coordinatesTable.item(0, 0).text() == "1.000"
    assert ruler.ui.coordinatesTable.item(1, 0).text() == "2.000"
    assert "1.414 in" in ruler.ui.statusLabel.text()
    assert (ruler.first, ruler.second) == original
    assert window.defaultUnits == "mm"
    ruler.ui.inchesCheck.setChecked(False)
    assert ruler.ui.coordinatesTable.item(0, 0).text() == "25.400"
    assert (ruler.first, ruler.second) == original


def _double_click_coordinate(ruler, row, column, text):
    table = ruler.ui.coordinatesTable
    item = table.item(row, column)
    position = table.visualItemRect(item).center()
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=position)
    QTest.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=position)
    editor = next((widget for widget in table.findChildren(QLineEdit) if widget.isVisible()), None)
    assert editor is not None and editor.isVisible()
    QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(editor, text)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()


def test_double_click_editing_creates_coordinates_and_recalculates_ruler(window, qt_app):
    window.viewTop()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    qt_app.processEvents()
    _double_click_coordinate(ruler, 0, 0, "10")
    assert ruler.first == (10, 0, 0) and ruler.second is None
    _double_click_coordinate(ruler, 1, 0, "13")
    qt_app.processEvents()
    _double_click_coordinate(ruler, 1, 1, "4")
    assert ruler.second == (13, 4, 0) and ruler.fixed
    assert "5.000 mm" in ruler.ui.statusLabel.text()
    np.testing.assert_allclose(ruler.line.pos, [ruler.first, ruler.second])
    for column in range(3):
        assert not ruler.ui.coordinatesTable.item(2, column).flags() & Qt.ItemFlag.ItemIsEditable
    ruler.ui.inchesCheck.setChecked(True)
    qt_app.processEvents()
    _double_click_coordinate(ruler, 1, 0, "2")
    assert ruler.second[0] == pytest.approx(50.8)
    assert ruler.first[0] == 10


def test_lathe_coordinate_edit_uses_diameter_and_rejects_invalid_input(window):
    window.ui.actionLatheMode.setChecked(True)
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    ruler.ui.coordinatesTable.item(0, 0).setText("20")
    ruler.ui.coordinatesTable.item(1, 0).setText("30")
    ruler.ui.coordinatesTable.item(1, 2).setText("12")
    assert ruler.first == (10, 0, 0) and ruler.second == (15, 0, 12)
    assert "13.000 mm" in ruler.ui.statusLabel.text()
    original = ruler.first, ruler.second
    for text in ("invalid", "nan", "inf"):
        ruler.ui.coordinatesTable.item(1, 0).setText(text)
        assert (ruler.first, ruler.second) == original
        assert ruler.ui.coordinatesTable.item(1, 0).text() == "30.000"
    ruler.ui.coordinatesTable.item(1, 2).setText("12,5")
    assert ruler.second[2] == 12.5


def test_front_to_lathe_resets_measurement_even_though_both_use_xz(window):
    window.viewFront()
    window.ui.actionMeasure.trigger()
    ruler = window._ruler
    ruler.first, ruler.second = (10, 0, 0), (20, 0, 10)
    ruler.fixed = True
    window.ui.actionLatheMode.setChecked(True)
    assert ruler.plane == "xz" and ruler.first is None and not ruler.fixed


def test_ruler_uses_displayed_clipped_mesh_and_ignores_hidden_objects(window, qt_app):
    triangles = np.array([[(-10, -10, 0), (10, -10, 0), (0, 10, 0)]])
    window._add_stl_mesh(mesh_from_triangles(triangles), "Facet")
    window.viewTop()
    window.ui.actionMeasure.trigger()
    point = QPointF(_screen(window, (0, 0, 0)))
    assert window._ruler.pick(point) == pytest.approx((0, 0, 0), abs=0.1)
    entry = window._stl_entries[0]
    entry.overlay.item.setGLOptions("translucent")
    assert window._ruler.pick(point) is not None
    window._section_selected_stl("X", 2.0, True)
    assert entry.section_overlay is not None
    assert window._ruler.pick(point) is None
    clipped_point = QPointF(_screen(window, (4, -5, 0)))
    assert window._ruler.pick(clipped_point) is not None
    entry.section_overlay.item.setVisible(False)
    assert window._ruler.pick(clipped_point) is None
