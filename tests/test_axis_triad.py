from __future__ import annotations

import pytest
from OpenGL import GL

from app.ui.axis_triad import (
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
