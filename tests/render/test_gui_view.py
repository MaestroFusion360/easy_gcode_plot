"""GUI camera, fit-to-view, and plot context behavior."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QMatrix4x4, QVector3D, QVector4D
from PyQt6.QtWidgets import QApplication

from app.gcode.trace_tools import RenderPoint
from app.main_window import MainWindow

# These tests inspect internal camera mappings while validating fixed views.
# pylint: disable=protected-access


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
    window.ui.graphicsView.setProjectionMode("perspective")
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


def test_milling_3d_zoom_changes_parallel_span_without_changing_fov(qt_app):
    window = MainWindow()
    window.ui.actionLatheMode.setChecked(False)
    qt_app.processEvents()

    view = window.ui.graphicsView
    window.view3d()
    assert view.isOrthographic()
    view.opts["fov"] = 60.0
    original_distance = float(view.opts["distance"])
    original_width = view.orthographicWidth()

    window.zoomIn()

    assert view.opts["fov"] == pytest.approx(60.0)
    assert view.opts["distance"] == pytest.approx(original_distance)
    assert view.orthographicWidth() == pytest.approx(original_width * 0.9)
    window.deleteLater()


def test_milling_3d_parallel_projection_preserves_size_across_depth_and_orbit(qt_app):
    window = MainWindow()
    try:
        window.ui.actionLatheMode.setChecked(False)
        window.ui.graphicsView.resize(800, 500)
        window.view3d()
        view = window.ui.graphicsView
        assert view.isOrthographic()

        def screen_length(y):
            start = window._project_world_to_screen(0, y, 0)  # pylint: disable=protected-access
            end = window._project_world_to_screen(10, y, 0)  # pylint: disable=protected-access
            return ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5

        assert screen_length(0) == pytest.approx(screen_length(20), rel=1e-6)
        view.orbit(20, 10)
        assert view.isOrthographic()
        assert screen_length(0) == pytest.approx(screen_length(20), rel=1e-6)
    finally:
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


def test_orthographic_clipping_remains_safe_across_orbit_angles(qt_app):
    window = MainWindow()
    try:
        window.latheMode = False
        window._view_mode = "3d"  # pylint: disable=protected-access
        view = window.ui.graphicsView
        view.resize(800, 400)
        view.setProjectionMode("orthographic")
        bounds = ((800.0, 820.0), (20.0, 40.0), (-30.0, -10.0))
        window.render_points = [
            RenderPoint(bounds[0][0], bounds[1][0], bounds[2][0], None, 0, 0),
            RenderPoint(bounds[0][1], bounds[1][1], bounds[2][1], None, 1, 1),
        ]

        window.fitToView()
        orthographic_width = view._orthographic_width  # pylint: disable=protected-access
        near_clip = view._orthographic_near  # pylint: disable=protected-access
        far_clip = view._orthographic_far  # pylint: disable=protected-access

        for azimuth, elevation in ((170, 70), (-250, 20), (90, -130), (320, 80)):
            view.orbit(azimuth, elevation)
            matrix = view.viewMatrix()
            camera_depths = [
                -(matrix * QVector4D(x, y, z, 1.0)).z() for x in bounds[0] for y in bounds[1] for z in bounds[2]
            ]
            camera_depths.append(-(matrix * QVector4D(0.0, 0.0, 0.0, 1.0)).z())

            assert min(camera_depths) >= near_clip
            assert max(camera_depths) <= far_clip
            assert view._orthographic_near == near_clip  # pylint: disable=protected-access
            assert view._orthographic_far == far_clip  # pylint: disable=protected-access
            assert view._orthographic_width == orthographic_width  # pylint: disable=protected-access
    finally:
        window.deleteLater()


def test_grid_is_only_available_in_fixed_and_lathe_views(qt_app):
    window = MainWindow()
    try:
        window.latheMode = False
        window.plotGrid = True
        window._view_mode = "3d"  # pylint: disable=protected-access
        window.loadPlot()
        assert window._milling_grid_item is None  # pylint: disable=protected-access
        assert not window.ui.actionGrid.isEnabled()

        window.viewTop()
        assert window._milling_grid_item is not None  # pylint: disable=protected-access
        assert window._milling_grid_item.visible()  # pylint: disable=protected-access
        assert window.ui.actionGrid.isEnabled()

        window.viewFront()
        assert window._milling_grid_item.visible()  # pylint: disable=protected-access
        window.viewLeft()
        assert window._milling_grid_item.visible()  # pylint: disable=protected-access

        window.view3d()
        assert not window._milling_grid_item.visible()  # pylint: disable=protected-access
        assert not window.ui.actionGrid.isEnabled()

        window.latheMode = True
        window._view_mode = "lathe"  # pylint: disable=protected-access
        window.loadPlot()
        assert window._lathe_grid_item is not None  # pylint: disable=protected-access
        assert window._lathe_grid_item.visible()  # pylint: disable=protected-access
        assert window.ui.actionGrid.isEnabled()
    finally:
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


def _camera_axis_signature(window):
    matrix = window.ui.graphicsView.viewMatrix()
    signature = []
    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        point = matrix * QVector4D(*axis, 0.0)
        signature.extend((point.x(), point.y(), point.z()))
    return tuple(signature)


@pytest.mark.parametrize(
    ("kinematics", "expected"),
    [
        (None, {"top": "xy", "front": "xz", "left": "yz"}),
        ("4ax_table_a", {"top": "xy", "front": "xz", "left": "yz"}),
        ("4ax_table_c", {"top": "xy", "front": "xz", "left": "yz"}),
        ("4ax_table_b", {"top": "xy", "front": "xz", "left": "yz"}),
    ],
)
def test_milling_physical_views_map_to_expected_world_planes(qt_app, kinematics, expected):
    window = MainWindow()
    previous = window.rotaryKinematics
    try:
        window.rotaryKinematics = kinematics
        assert {mode: window._milling_view_plane(mode) for mode in ("top", "front", "left")} == expected
    finally:
        window.rotaryKinematics = previous
        window.deleteLater()


def test_table_b_top_and_front_use_spindle_side_camera_orientation(qt_app):
    window = MainWindow()
    previous = window.rotaryKinematics
    try:
        window.rotaryKinematics = None
        window.viewTop()
        vertical_top = _camera_axis_signature(window)
        window.viewFront()
        window.viewLeft()
        vertical_left = _camera_axis_signature(window)

        window.rotaryKinematics = "4ax_table_b"
        window.viewTop()
        # Top is XY/G17, using the spindle-side Front camera orientation.
        assert window._milling_view_plane() == "xy"
        assert _camera_axis_signature(window) == pytest.approx(vertical_top, abs=1e-6)
        assert window.ui.actionTop.toolTip().endswith("(XY/G17)")

        window.viewFront()
        # Front is XZ/G18, with X right and Z down in the horizontal mill view.
        assert window._milling_view_plane() == "xz"
        assert window.ui.graphicsView.cameraPosition().y() > 0
        assert window.ui.actionFront.toolTip().endswith("(XZ/G18)")

        window.viewLeft()
        assert _camera_axis_signature(window) == pytest.approx(vertical_left, abs=1e-6)
        assert window.ui.actionLeft.toolTip().endswith("(YZ/G19)")
    finally:
        window.rotaryKinematics = previous
        window.deleteLater()


def test_switching_to_table_b_reapplies_current_fixed_physical_view(qt_app):
    window = MainWindow()
    previous = window.rotaryKinematics
    try:
        window._select_rotary_kinematics(None)
        window.viewFront()
        window.viewTop()
        vertical_top = _camera_axis_signature(window)
        assert window._view_mode == "top"  # pylint: disable=protected-access

        window._select_rotary_kinematics("4ax_table_b")

        assert window._view_mode == "top"  # pylint: disable=protected-access
        assert _camera_axis_signature(window) == pytest.approx(vertical_top, abs=1e-6)
        assert window.ui.actionTop.toolTip().endswith("(XY/G17)")
        assert window.ui.actionFront.toolTip().endswith("(XZ/G18)")
    finally:
        window._select_rotary_kinematics(previous)
        window.deleteLater()


@pytest.mark.parametrize("vertical_profile", [None, "4ax_table_a", "4ax_table_c"])
@pytest.mark.parametrize("view_method", ["viewTop", "viewFront", "viewLeft"])
def test_switching_from_table_b_restores_vertical_mapping_for_active_view(qt_app, vertical_profile, view_method):
    window = MainWindow()
    previous = window.rotaryKinematics
    try:
        window._select_rotary_kinematics("4ax_table_b")
        getattr(window, view_method)()
        assert window._milling_view_plane() == {"viewTop": "xy", "viewFront": "xz", "viewLeft": "yz"}[view_method]

        window._select_rotary_kinematics(vertical_profile)

        assert window._view_mode == {"viewTop": "top", "viewFront": "front", "viewLeft": "left"}[view_method]
        assert window._milling_view_plane() == {"viewTop": "xy", "viewFront": "xz", "viewLeft": "yz"}[view_method]
        expected_label = {"viewTop": "(XY/G17)", "viewFront": "(XZ/G18)", "viewLeft": "(YZ/G19)"}[view_method]
        action = {"viewTop": window.ui.actionTop, "viewFront": window.ui.actionFront, "viewLeft": window.ui.actionLeft}[
            view_method
        ]
        assert action.toolTip().endswith(expected_label)
        expected_left = _camera_signature_for_look_at((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        assert _camera_axis_signature(window) == pytest.approx(
            {
                "viewTop": _camera_signature_for(90.0, -90.0),
                "viewFront": _camera_signature_for(0.0, -90.0),
                "viewLeft": expected_left,
            }[view_method],
            abs=1e-6,
        )
    finally:
        window._select_rotary_kinematics(previous)
        window.deleteLater()


def _camera_signature_for(elevation, azimuth):
    """Return the expected GL view rotation produced by camera angles."""
    matrix = QMatrix4x4()
    matrix.rotate(elevation - 90.0, 1.0, 0.0, 0.0)
    matrix.rotate(azimuth + 90.0, 0.0, 0.0, -1.0)
    signature = []
    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        point = matrix * QVector4D(*axis, 0.0)
        signature.extend((point.x(), point.y(), point.z()))
    return tuple(signature)


def _camera_signature_for_look_at(eye, up):
    """Return the expected GL view rotation for a fixed eye/up camera basis."""
    matrix = QMatrix4x4()
    matrix.lookAt(QVector3D(*eye), QVector3D(0.0, 0.0, 0.0), QVector3D(*up))
    signature = []
    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        point = matrix * QVector4D(*axis, 0.0)
        signature.extend((point.x(), point.y(), point.z()))
    return tuple(signature)


def test_table_b_grid_tracks_world_plane_of_physical_view(qt_app):
    window = MainWindow()
    previous = window.rotaryKinematics
    try:
        window.rotaryKinematics = "4ax_table_b"
        window.latheMode = False
        window.plotGrid = True
        window.plotGridStep = 10.0
        center = QVector3D(12.0, 23.0, 34.0)

        window.viewTop()
        window.ui.graphicsView.opts["center"] = center
        window._update_milling_grid()  # pylint: disable=protected-access
        assert window._milling_grid_center == pytest.approx((10.0, 20.0, 0.0))  # pylint: disable=protected-access

        window.viewFront()
        window.ui.graphicsView.opts["center"] = center
        window._update_milling_grid()  # pylint: disable=protected-access
        assert window._milling_grid_center == pytest.approx((10.0, 0.0, 30.0))  # pylint: disable=protected-access

        window.viewLeft()
        window.ui.graphicsView.opts["center"] = center
        window._update_milling_grid()  # pylint: disable=protected-access
        assert window._milling_grid_center == pytest.approx((0.0, 20.0, 30.0))  # pylint: disable=protected-access
    finally:
        window.rotaryKinematics = previous
        window.deleteLater()
