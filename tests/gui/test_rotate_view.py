"""Fixed-view rotation, command integration and per-document camera isolation."""

# pylint: disable=protected-access

import math

import numpy as np
import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QVector3D
from PyQt6.QtWidgets import QApplication, QDialog

from app.main_window import MainWindow
from app.ui.dialogs.rotate_view import RotateViewDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    owner = MainWindow()
    owner.autoUpdateEnabled = False
    yield owner
    owner.ui.editor.setModified(False)
    owner.autoUpdateTimer.stop()
    owner.deleteLater()
    qt_app.processEvents()


def orientation(view):
    return np.asarray(view.viewMatrix().copyDataTo()).reshape(4, 4)[:3, :3]


@pytest.mark.parametrize("mode", ["Top", "Front", "Left"])
@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
@pytest.mark.parametrize("angle", [90, -90, 180, 37.5])
def test_world_rotation_preserves_center_zoom_and_execution(window, mode, axis, angle, monkeypatch):
    window.ui.editor.setText("G0 X0 Y0 Z0\nG1 X20 Y30 Z40 F100\nM30")
    assert window.updateData(show_errors=False)
    getattr(window, "view" + mode)()
    view = window.ui.graphicsView
    view.opts["center"] = QVector3D(5, 6, 7)
    before = orientation(view)
    distance, width = view.opts["distance"], view.orthographicWidth()
    result, points = window.execution_result, window.render_points
    monkeypatch.setattr(window, "updateData", lambda **_kwargs: pytest.fail("Rotation must not execute CNC"))
    index = "XYZ".index(axis)
    direction = np.eye(3)[index]
    x, y, z = direction
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    cosine, sine = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    world_rotation = cosine * np.eye(3) + sine * cross + (1 - cosine) * np.outer(direction, direction)
    assert window.applyViewRotation(angle, axis)
    assert orientation(view) == pytest.approx(before @ world_rotation.T, abs=1e-6)
    assert view.opts["center"] == QVector3D(5, 6, 7)
    assert view.opts["distance"] == distance
    assert view.orthographicWidth() == width and view.isOrthographic()
    assert window.execution_result is result and window.render_points is points
    assert window.ui.actionRotateView.isEnabled()
    assert window.applyViewRotation(-angle, axis)
    assert orientation(view) == pytest.approx(before, abs=1e-6)


def test_command_locations_and_unsupported_modes(window, monkeypatch):
    action = window.ui.actionRotateView
    assert not action.isEnabled()
    assert not action.icon().isNull()
    assert action in window.ui.menu_View.actions()
    assert action in window.ui.viewToolBar.actions()
    assert "actionRotateView" in window.hotkeyActions
    assert window.toolbarSettings.commands["actionRotateView"][0] is action
    menus = []
    monkeypatch.setattr("app.ui.windows.main_window_plot.QMenu.exec", lambda menu, _point: menus.append(menu.actions()))
    window.plotContextMenu(QPoint(0, 0))
    assert action in menus[0]
    assert not window.applyViewRotation(90, "X")
    window.viewTop()
    assert action.isEnabled()
    window.ui.actionLatheMode.setChecked(True)
    assert not action.isEnabled()
    before = orientation(window.ui.graphicsView)
    assert not window.applyViewRotation(90, "X")
    assert orientation(window.ui.graphicsView) == pytest.approx(before)


def test_grid_and_ruler_follow_rotated_plane_and_standard_view_resets(window):
    window.viewTop()
    window.plotGrid = True
    window.viewTop()
    assert window.applyViewRotation(45, "X")
    assert window._milling_view_plane() is None
    assert not window.ui.actionGrid.isEnabled()
    assert not window.ui.actionMeasure.isEnabled()
    assert not window._milling_grid_item.visible()
    window.refreshPlotView()
    assert window._milling_grid_item is None
    assert window.applyViewRotation(45, "X")
    assert window._milling_view_plane() == "xz"
    assert window.ui.actionGrid.isEnabled() and window.ui.actionMeasure.isEnabled()
    assert window._milling_grid_item.visible()
    window.viewTop()
    assert not window._fixed_view_rotated
    assert window._milling_view_plane() == "xy"


def test_rotated_camera_survives_document_switch_and_visual_refresh(window):
    window.viewLeft()
    window.applyViewRotation(37, "Z")
    expected = orientation(window.ui.graphicsView)
    window.refreshPlotView()
    assert orientation(window.ui.graphicsView) == pytest.approx(expected)
    window.newFile()
    window.view3d()
    assert window._activate_document(0)
    assert orientation(window.ui.graphicsView) == pytest.approx(expected)
    assert window._fixed_view_rotated
    assert window.ui.actionRotateView.isEnabled()
    assert window._milling_view_plane() is None
    assert not window.ui.actionMeasure.isEnabled()
    assert window._activate_document(1)
    assert not window.ui.actionRotateView.isEnabled()


def test_dialog_defaults_cancel_and_accept(window, monkeypatch):
    window.viewFront()
    before = orientation(window.ui.graphicsView)
    captured = []

    def cancel(dialog):
        captured.append((dialog.angle.value(), dialog.axis.currentText()))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(RotateViewDialog, "exec", cancel)
    assert not window.rotateView()
    assert captured == [(90, "Y")]
    assert orientation(window.ui.graphicsView) == pytest.approx(before)

    def accept(dialog):
        dialog.angle.setValue(180)
        dialog.axis.setCurrentText("Y")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RotateViewDialog, "exec", accept)
    window.ui.actionRotateView.trigger()
    assert orientation(window.ui.graphicsView) != pytest.approx(before)
    assert window._milling_view_plane() == "xz"
