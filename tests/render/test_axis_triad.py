from __future__ import annotations

import pytest
from OpenGL import GL
from PyQt6.QtGui import QMatrix4x4, QVector3D, QVector4D
from pyqtgraph.opengl import GLMeshItem

from app.ui.plot.axis_triad import (
    AXIS_COLORS,
    AXIS_DEPTH,
    AXIS_LENGTH_PX,
    AXIS_OPAQUE_GL_OPTIONS,
    AXIS_ORIGIN_COLOR,
    AXIS_TEXT_GL_OPTIONS,
    AxisTriadItem,
)


def test_axis_triad_has_sphere_three_arrows_and_three_labels():
    item = AxisTriadItem()

    assert len(item._meshes) == 7  # pylint: disable=protected-access
    assert [label.text for label in item._labels] == ["X", "Y", "Z"]  # pylint: disable=protected-access
    assert len(item.childItems()) == 10


def test_axis_triad_center_updates_transform_without_rebuilding_children():
    item = AxisTriadItem()
    children = item.childItems()

    item.set_center((10.0, 20.0, 30.0))

    assert item.center == (10.0, 20.0, 30.0)
    assert item.childItems() == children


def test_axis_triad_world_extent_tracks_pixel_size_not_toolpath_size():
    class _View:
        def __init__(self, pixel_size):
            self.pixel_size = pixel_size

        def width(self):
            return 800

        def pixelSize(self, _position):
            return self.pixel_size

        def update(self):
            pass

    item = AxisTriadItem()
    item._setView(_View(0.25))  # pylint: disable=protected-access
    item.paint()
    assert item.extent == pytest.approx(AXIS_LENGTH_PX * 0.25)

    item.view().pixel_size = 2.0
    item.paint()
    assert item.extent == pytest.approx(AXIS_LENGTH_PX * 2.0)


def test_axis_triad_defaults_to_cnc_coordinate_origin():
    assert AxisTriadItem().center == (0.0, 0.0, 0.0)


def test_axis_triad_is_the_topmost_depth_independent_overlay():
    item = AxisTriadItem()

    assert item.depthValue() == AXIS_DEPTH
    assert AXIS_OPAQUE_GL_OPTIONS[GL.GL_DEPTH_TEST] is False
    assert AXIS_TEXT_GL_OPTIONS[GL.GL_DEPTH_TEST] is False
    assert item._meshes[0]._GLGraphicsItem__glOpts[GL.GL_DEPTH_TEST] is False  # pylint: disable=protected-access
    assert item._labels[0]._GLGraphicsItem__glOpts[GL.GL_DEPTH_TEST] is False  # pylint: disable=protected-access


def test_axis_triad_uses_fixed_unlit_colors():
    item = AxisTriadItem()

    expected = [
        AXIS_ORIGIN_COLOR,
        AXIS_COLORS["X"],
        AXIS_COLORS["X"],
        AXIS_COLORS["Y"],
        AXIS_COLORS["Y"],
        AXIS_COLORS["Z"],
        AXIS_COLORS["Z"],
    ]
    assert [mesh.opts["color"] for mesh in item._meshes] == expected  # pylint: disable=protected-access
    assert all(mesh.opts["shader"] is None for mesh in item._meshes)  # pylint: disable=protected-access
    assert [label.color for label in item._labels] == [  # pylint: disable=protected-access
        AXIS_COLORS["X"],
        AXIS_COLORS["Y"],
        AXIS_COLORS["Z"],
    ]


@pytest.mark.parametrize("elevation,azimuth", [(30, -45), (60, 45), (-30, 135), (0, 0)])
def test_empty_scene_arrows_survive_camera_depth_clipping(monkeypatch, elevation, azimuth):
    projection = QMatrix4x4()
    projection.ortho(-50, 50, -50, 50, 0.01, 2)
    camera = QMatrix4x4()
    camera.translate(0, 0, -1)
    camera.rotate(elevation, 1, 0, 0)
    camera.rotate(azimuth, 0, 0, 1)
    item = AxisTriadItem()
    item.set_center((0, 0, 0))
    item.scale(12, 12, 12)
    clipped = False
    for mesh in item._meshes:  # pylint: disable=protected-access
        original = projection * camera * item.transform() * mesh.transform()
        monkeypatch.setattr(GLMeshItem, "mvpMatrix", lambda _self, matrix=original: QMatrix4x4(matrix))
        overlay = mesh.mvpMatrix()
        for vertex in mesh.opts["meshdata"].vertexes():
            point = QVector4D(QVector3D(*map(float, vertex)), 1)
            before, after = original * point, overlay * point
            clipped |= abs(before.z()) > before.w()
            assert abs(after.z()) <= after.w()
            assert (after.x(), after.y(), after.w()) == pytest.approx((before.x(), before.y(), before.w()))
    assert clipped, "Regression must exercise arrows outside the scene depth range"
