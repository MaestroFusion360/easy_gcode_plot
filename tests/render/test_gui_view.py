"""GUI camera, fit-to-view, and plot context behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QVector3D
from PyQt6.QtWidgets import QApplication

from app.gcode.trace_tools import RenderPoint
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_switching_from_lathe_to_empty_milling_recenters_camera_on_axis_origin(qt_app):
    window = MainWindow()
    window.plotAxes = True
    window.ui.actionLatheMode.setChecked(True)
    window.ui.editor.clear()

    # Reproduce a camera center left by fitting turning stock away from the
    # world origin. The triad itself remains anchored at (0, 0, 0).
    window.ui.graphicsView.opts["center"] = QVector3D(120.0, 0.0, -80.0)
    axis_item = window._axis_triad_item  # pylint: disable=protected-access
    assert axis_item.center == (0.0, 0.0, 0.0)

    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()

    center = window.ui.graphicsView.opts["center"]
    assert window.latheMode is False
    assert (center.x(), center.y(), center.z()) == pytest.approx((0.0, 0.0, 0.0))
    assert window._axis_triad_item is axis_item  # pylint: disable=protected-access
    assert axis_item.center == (0.0, 0.0, 0.0)
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


def test_lathe_fit_keeps_tall_stock_inside_widescreen_viewport(qt_app):
    window = MainWindow()
    window.latheMode = True
    window._view_mode = "lathe"  # pylint: disable=protected-access
    window.stockConfigured = False
    window._stock_auto_suggestion = None  # pylint: disable=protected-access
    window.render_points = [
        RenderPoint(-152.5, 0.0, -222.7, None, 0, 0),
        RenderPoint(152.5, 0.0, 2.0, None, 1, 1),
    ]
    window.ui.graphicsView.resize(1536, 900)
    window.ui.graphicsView.opts["fov"] = 0.01

    window.fitToView()

    width = window.ui.graphicsView.width()
    height = window.ui.graphicsView.height()
    for x in (-152.5, 152.5):
        for z in (-222.7, 2.0):
            screen = window._project_world_to_screen(x, 0.0, z)  # pylint: disable=protected-access
            assert screen is not None
            assert 0.04 * width <= screen[0] <= 0.96 * width
            assert 0.04 * height <= screen[1] <= 0.96 * height
    window.deleteLater()


def test_lathe_zoom_uses_camera_distance_without_changing_near_zero_fov(qt_app):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(True)
    qt_app.processEvents()

    view = window.ui.graphicsView
    assert view.projectionMode() == "perspective"
    assert view.opts["fov"] == pytest.approx(0.01)

    original_distance = float(view.opts["distance"])
    original_center = QVector3D(view.opts["center"])
    original_rotation = view.opts["rotation"]

    window.zoomIn()

    assert view.opts["fov"] == pytest.approx(0.01)
    assert view.opts["distance"] == pytest.approx(original_distance * 0.9)
    assert view.opts["center"] == original_center
    assert view.opts["rotation"] == original_rotation

    zoomed_distance = float(view.opts["distance"])
    window.zoomOut()

    assert view.opts["fov"] == pytest.approx(0.01)
    assert view.opts["distance"] == pytest.approx(zoomed_distance * 1.1)
    assert view.opts["center"] == original_center
    assert view.opts["rotation"] == original_rotation
    window.deleteLater()


def test_milling_3d_zoom_keeps_existing_fov_behavior(qt_app):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()

    view = window.ui.graphicsView
    view.opts["fov"] = 60.0
    original_distance = float(view.opts["distance"])

    window.zoomIn()

    assert view.opts["fov"] < 60.0
    assert view.opts["distance"] == pytest.approx(original_distance)
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
    monkeypatch.setattr("app.ui.windows.main_window_plot.QMenu", Menu)
    window.plotContextMenu(QPoint())
    assert captured[0] is window.ui.actionFitToView
    window.deleteLater()
