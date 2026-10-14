"""Depth picking and mouse gestures share the existing playback selection."""

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QMatrix4x4, QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from app.gcode.kernel import execute
from app.gcode.trace import render_trace
from app.ui.plot.plot_navigation import PlotNavigation
from app.ui.plot.toolpath_vbo import ToolpathSegment, segments_from_render_points
from app.ui.plot.trace_picking import TracePicker


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _segment(depth, index=0, move=1):
    return ToolpathSegment((-0.8, 0, depth), (0.8, 0, depth), index, move)


def test_picking_prefers_front_depth_and_ignores_hidden_rapids():
    picker = TracePicker((_segment(0.5, 3), _segment(-0.5, 8, 0)))
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100)) == 8
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100), show_rapid=False) == 3
    assert picker.pick((50, 90), QMatrix4x4(), (0, 0, 100, 100)) is None


def test_picking_respects_playback_visibility_and_flat_view_distance():
    picker = TracePicker((_segment(0.5, 0), _segment(-0.5, 1)), (4, 9))
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100), visible_count=5) == 0
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100), visible_count=0) is None
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100), visible_count=10) == 1
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100), depth_aware=False) == 0


def test_picking_does_not_bridge_discontinuous_motion_starts():
    motions = [SimpleNamespace(start_x=x, start_y=0, start_z=0, move=1, tool=None) for x in (-0.9, 0.6)]
    points = [SimpleNamespace(x=x, y=0, z=0, motion_index=index) for x, index in ((-0.9, 0), (-0.6, 0), (0.9, 1))]
    picker = TracePicker(segments_from_render_points(points, motions))
    assert picker.pick((50, 50), QMatrix4x4(), (0, 0, 100, 100), depth_aware=False) is None


def test_picking_clips_near_and_far_planes_including_crossing_lines():
    crossing = ToolpathSegment((-0.8, 0, -2), (0.8, 0, 0), 7, 1)
    picker = TracePicker((_segment(-3, 1), _segment(3, 2), crossing))
    assert picker.pick((75, 50), QMatrix4x4(), (0, 0, 100, 100)) == 7
    assert picker.pick((20, 50), QMatrix4x4(), (0, 0, 100, 100)) is None
    assert TracePicker(()).pick((50, 50), QMatrix4x4(), (0, 0, 100, 100)) is None


def test_perspective_picking_rejects_geometry_behind_camera():
    matrix = QMatrix4x4()
    matrix.perspective(60, 1, 0.1, 100)
    picker = TracePicker((_segment(2, 1), _segment(-2, 2)))
    assert picker.pick((50, 50), matrix, (0, 0, 100, 100)) == 2


def test_sampled_arc_picking_selects_the_owning_kernel_motion():
    result = execute("G17 G90 G0 X1 Y0 Z0\nG3 X0 Y1 I-1 J0 F100\nM30", language="fanuc_mill")
    assert result.ok, result.diagnostics
    segments = segments_from_render_points(render_trace(result), result.motions)
    picker = TracePicker(segments)
    index = picker.pick((85.355, 14.645), QMatrix4x4(), (0, 0, 100, 100))
    assert index is not None and result.motions[index].move == 3
    assert result.motions[index].source_block == 1


def _mouse(view, kind, position, button, buttons, modifiers=Qt.KeyboardModifier.NoModifier):
    point = QPointF(*position)
    event = QMouseEvent(kind, point, point, button, buttons, modifiers)
    QApplication.sendEvent(view, event)


@pytest.mark.parametrize("cimco", [False, True])
def test_click_selects_and_drag_uses_the_selected_mode(qt_app, cimco):
    view = QWidget()
    selected, pans, menus = [], [], []
    view.pan = lambda *args, **kwargs: pans.append((args, kwargs))
    view.customContextMenuRequested.connect(menus.append)
    navigation = PlotNavigation(view, on_pick=selected.append, cimco_like=lambda: cimco)
    view.installEventFilter(navigation)
    left, right = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
    modifiers = Qt.KeyboardModifier.NoModifier if cimco else Qt.KeyboardModifier.ShiftModifier
    _mouse(view, QEvent.Type.MouseButtonPress, (20, 20), left, left, modifiers)
    _mouse(view, QEvent.Type.MouseButtonRelease, (20, 20), left, Qt.MouseButton.NoButton, modifiers)
    assert len(selected) == 1 and not pans
    pan_button = right if cimco else left
    _mouse(view, QEvent.Type.MouseButtonPress, (20, 20), pan_button, pan_button)
    _mouse(view, QEvent.Type.MouseMove, (60, 40), Qt.MouseButton.NoButton, pan_button)
    _mouse(view, QEvent.Type.MouseButtonRelease, (60, 40), pan_button, Qt.MouseButton.NoButton)
    assert pans and len(selected) == 1 and not menus
    view.deleteLater()
    qt_app.processEvents()


def test_cimco_right_click_menu_is_distinct_from_drag_and_left_drag_does_not_pick(qt_app):
    view = QWidget()
    menus, selected = [], []
    view.pan = lambda *args, **kwargs: None
    view.customContextMenuRequested.connect(menus.append)
    navigation = PlotNavigation(view, on_pick=selected.append, cimco_like=lambda: True)
    view.installEventFilter(navigation)
    left, right = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
    _mouse(view, QEvent.Type.MouseButtonPress, (20, 20), right, right)
    _mouse(view, QEvent.Type.MouseButtonRelease, (21, 20), right, Qt.MouseButton.NoButton)
    assert len(menus) == 1
    context = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPointF(21, 20).toPoint())
    assert navigation.eventFilter(view, context)
    _mouse(view, QEvent.Type.MouseButtonPress, (20, 20), right, right)
    _mouse(view, QEvent.Type.MouseMove, (60, 40), Qt.MouseButton.NoButton, right)
    _mouse(view, QEvent.Type.MouseMove, (20, 20), Qt.MouseButton.NoButton, right)
    _mouse(view, QEvent.Type.MouseButtonRelease, (20, 20), right, Qt.MouseButton.NoButton)
    assert len(menus) == 1
    _mouse(view, QEvent.Type.MouseButtonPress, (20, 20), left, left)
    _mouse(view, QEvent.Type.MouseMove, (60, 40), Qt.MouseButton.NoButton, left)
    _mouse(view, QEvent.Type.MouseButtonRelease, (60, 40), left, Qt.MouseButton.NoButton)
    assert not selected
    view.deleteLater()
    qt_app.processEvents()


def test_cimco_preserves_keyboard_menu_and_cancels_gesture_on_focus_loss(qt_app):
    view = QWidget()
    menus, picks = [], []
    view.customContextMenuRequested.connect(menus.append)
    navigation = PlotNavigation(view, on_pick=picks.append, cimco_like=lambda: True)
    view.installEventFilter(navigation)
    keyboard = QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, QPointF(10, 10).toPoint())
    assert not navigation.eventFilter(view, keyboard)
    left = Qt.MouseButton.LeftButton
    _mouse(view, QEvent.Type.MouseButtonPress, (20, 20), left, left)
    QApplication.sendEvent(view, QEvent(QEvent.Type.FocusOut))
    _mouse(view, QEvent.Type.MouseButtonRelease, (20, 20), left, Qt.MouseButton.NoButton)
    assert not picks and not menus
    view.deleteLater()
    qt_app.processEvents()
