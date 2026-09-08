from __future__ import annotations

import pytest

from app.ui.axis_triad import AXIS_LENGTH_PX, AxisTriadItem


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
