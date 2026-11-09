"""Orientation cube widget and plot-view integration tests."""

# These tests inspect the cube's hit regions and the window's camera state.
# pylint: disable=protected-access

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMatrix4x4, QQuaternion, QVector3D, QVector4D
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.plot.view_cube import ViewCube


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _eye(yaw, pitch):
    azimuth, elevation = math.radians(yaw), math.radians(pitch)
    return (
        math.cos(elevation) * math.cos(azimuth),
        math.cos(elevation) * math.sin(azimuth),
        math.sin(elevation),
    )


def test_view_cube_emits_all_face_edge_and_corner_views(qt_app):
    cube = ViewCube()
    cube.show()
    qt_app.processEvents()
    signals = []
    cube.viewRequested.connect(lambda yaw, pitch: signals.append((yaw, pitch)))

    directions = set()
    for yaw, pitch in ((43.0, 28.0), (223.0, -28.0)):
        cube.set_orientation(yaw, pitch)
        regions = [(patch.boundingRect().center().toPoint(), direction) for patch, direction, _ in cube._regions()]
        for point, direction in regions:
            signals.clear()
            QTest.mouseClick(cube, Qt.MouseButton.LeftButton, pos=point)
            assert len(signals) == 1
            length = math.sqrt(sum(value * value for value in direction))
            assert _eye(*signals[0]) == pytest.approx(tuple(value / length for value in direction))
            directions.add(direction)

    assert len(directions) == 26
    signals.clear()
    QTest.mouseDClick(cube, Qt.MouseButton.LeftButton, pos=cube.rect().center())
    assert signals == [(43.0, 28.0)]
    assert not cube.grab().isNull()
    cube.deleteLater()


def test_view_cube_tracks_the_rolled_basis_of_a_quaternion_camera(qt_app):
    window = MainWindow()
    try:
        view = window.ui.graphicsView
        basis = QMatrix4x4()
        basis.lookAt(QVector3D(-1, 1, 1), QVector3D(0, 0, 0), QVector3D(0, 1, 0))
        view.opts["rotationMethod"] = "quaternion"
        view.setCameraPosition(rotation=QQuaternion.fromRotationMatrix(basis.normalMatrix()))
        window._sync_view_cube()

        inverse = view.viewMatrix().inverted()[0]
        right = inverse * QVector4D(1.0, 0.0, 0.0, 0.0)
        up = inverse * QVector4D(0.0, 1.0, 0.0, 0.0)
        cube = window._view_cube
        assert cube._basis == pytest.approx((right.x(), right.y(), right.z(), up.x(), up.y(), up.z()))
    finally:
        window.deleteLater()


def test_main_window_places_the_cube_and_applies_a_clicked_view(qt_app):
    window = MainWindow()
    try:
        window.ui.actionLatheMode.setChecked(False)
        window.ui.graphicsView.resize(900, 600)
        qt_app.processEvents()
        cube = window._view_cube
        assert cube.parent() is window.ui.graphicsView
        assert not cube.isHidden()
        assert cube.x() + cube.width() <= window.ui.graphicsView.width()
        assert cube.y() == 12

        point = next(
            patch.boundingRect().center().toPoint()
            for patch, direction, _label in cube._regions()
            if direction == (0, 0, 1)
        )
        QTest.mouseClick(cube, Qt.MouseButton.LeftButton, pos=point)
        view = window.ui.graphicsView
        assert view.opts["rotationMethod"] == "euler"
        assert view.opts["elevation"] == pytest.approx(90.0)
        assert window._view_mode == "3d"
        assert window.ui.action3D.isChecked()
        assert (cube.yaw, cube.pitch) == pytest.approx((-90.0, 90.0))

        window.ui.actionLatheMode.setChecked(True)
        qt_app.processEvents()
        assert cube.isHidden()
        window.ui.actionLatheMode.setChecked(False)
        qt_app.processEvents()
        assert not cube.isHidden()
    finally:
        window.deleteLater()
