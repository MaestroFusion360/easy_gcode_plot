"""Turning stock mesh spans and profile-break geometry."""

import pytest

from app.gcode.kernel import TraceMotion
from app.gcode.stock import TurningStockSpec, TurningStockTimeline, profile_interval_mesh_spans
from app.ui.plot.stock_overlay import material_interval_mesh_spans


def test_radial_groove_records_exact_vertical_stock_walls():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=0.5),
        {"T0404": {"type": "groove", "applications": ["od"], "width": 4.0, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.profile_breaks == pytest.approx((-10.0, -6.0))


def test_groove_wall_mesh_is_vertical_instead_of_interpolated_bevel():
    spans = profile_interval_mesh_spans(
        -10.5,
        -10.0,
        0.0,
        25.0,
        0.0,
        15.0,
        (-10.0,),
    )

    assert len(spans) == 1
    assert spans[0] == pytest.approx((-10.5, -10.0, 0.0, 25.0, 0.0, 25.0))


def test_diagonal_groove_trace_does_not_create_false_vertical_breaks():
    motion = TraceMotion(1, 50.0, -5.0, 30.0, -15.0, tool="T0404", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=30, resolution=0.5),
        {"T0404": {"type": "groove", "applications": ["od"], "width": 4.0, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.profile_breaks == ()


def test_groove_mesh_cell_bounded_by_two_walls_does_not_reverse_into_a_wedge():
    spans = profile_interval_mesh_spans(
        -57.5,
        -57.0,
        37.75,
        50.0,
        41.225,
        50.0,
        (-57.5, -57.0),
    )

    assert len(spans) == 1
    assert spans[0] == pytest.approx((-57.5, -57.0, 37.75, 50.0, 37.75, 50.0))


def test_interval_mesh_does_not_cross_connect_one_profile_to_two_rings():
    spans = material_interval_mesh_spans(((0.0, 30.0),), ((0.0, 17.0), (20.0, 30.0)))

    assert spans == ((0.0, 17.0, 0.0, 17.0), (20.0, 30.0, 20.0, 30.0))


def test_interval_mesh_preserves_sloped_profiles_when_topology_matches():
    spans = material_interval_mesh_spans(((2.0, 20.0), (24.0, 30.0)), ((3.0, 19.0), (23.0, 29.0)))

    assert spans == ((2.0, 20.0, 3.0, 19.0), (24.0, 30.0, 23.0, 29.0))


def test_interval_mesh_reaches_exact_face_break_when_next_slice_is_empty():
    spans = material_interval_mesh_spans(((0.0, 12.4),), (), end_break=True)

    assert spans == ((0.0, 12.4, 0.0, 12.4),)
