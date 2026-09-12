"""Regression tests for axisymmetric turning Stock Removal."""

import math

import pytest

from app.gcode.kernel import TraceMotion
from app.gcode.stock import TurningStockSpec, TurningStockTimeline, profile_interval_mesh_spans
from app.gcode.turning_tool_geometry import cutting_insert_points, display_tool_geometry, turning_tool_polygon


def _at(timeline, z_value):
    return min(range(len(timeline.z)), key=lambda index: abs(timeline.z[index] - z_value))


def test_od_cut_reduces_outer_profile_and_rewinds():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool="T0101", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}},
    )
    stock.set_motion_count(1)
    assert stock.outer[_at(stock, -10)] == pytest.approx(20.0, abs=0.02)
    stock.set_motion_count(0)
    assert stock.outer == stock.initial_outer


def test_id_cut_increases_bore_without_changing_outer_profile():
    motion = TraceMotion(1, 20.0, 0.0, 30.0, -20.0, tool="T0202", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, inner_diameter=20, length=40, resolution=1),
        {"T0202": {"type": "id_80", "noseRadius": 0.4, "tipOrientation": 2}},
    )
    stock.set_motion_count(1)
    assert stock.inner[_at(stock, -10)] > 10.0
    assert stock.outer == stock.initial_outer


def test_drill_opens_dynamic_inner_profile():
    motion = TraceMotion(1, 0.0, 0.0, 0.0, -20.0, tool="T0303", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0303": {"type": "drill", "diameter": 10.0, "length": 50.0, "tipAngle": 118.0}},
    )
    stock.set_motion_count(1)
    assert stock.inner[_at(stock, -10)] == pytest.approx(5.0)
    assert stock.outer == stock.initial_outer


def test_od_groove_width_removes_outer_material_and_rewinds():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0404": {"type": "od_groove", "width": 4.0, "noseRadius": 5.0}},
    )
    stock.set_motion_count(1)
    assert stock.outer[_at(stock, -10)] == pytest.approx(15.0)
    assert stock.outer[_at(stock, -6)] == pytest.approx(15.0)
    assert stock.outer[_at(stock, -11)] == pytest.approx(25.0)
    stock.set_motion_count(0)
    assert stock.outer == stock.initial_outer


def test_id_groove_width_removes_inner_material():
    motion = TraceMotion(1, 20.0, -10.0, 30.0, -10.0, tool="T0505", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, inner_diameter=20, length=40, resolution=1),
        {
            "T0505": {
                "type": "id_groove",
                "width": 3.0,
            }
        },
    )
    stock.set_motion_count(1)
    assert stock.inner[_at(stock, -10)] == pytest.approx(15.0)
    assert stock.inner[_at(stock, -7)] == pytest.approx(15.0)
    assert stock.inner[_at(stock, -11)] == pytest.approx(10.0)
    assert stock.outer == stock.initial_outer


@pytest.mark.parametrize(
    ("tool_type", "insert_angle", "edge_angle", "radial_sign"),
    [("od_80", 80.0, 5.0, 1.0), ("id_80", 80.0, 5.0, -1.0), ("od_35", 35.0, 3.0, 1.0), ("id_35", 35.0, 3.0, -1.0)],
)
def test_cutting_insert_has_fixed_angle_and_main_edge_at_tip(tool_type, insert_angle, edge_angle, radial_sign):
    points = cutting_insert_points(
        4.0,
        insert_angle,
        edge_angle,
        3,
        internal=tool_type.startswith("id_"),
    )
    tip = points[0]
    main = points[1]
    other = points[3]
    assert tip == pytest.approx((0.0, 0.0))
    assert main[0] * radial_sign > 0.0
    assert math.degrees(math.atan2(abs(main[1]), abs(main[0]))) == pytest.approx(edge_angle)
    dot = main[0] * other[0] + main[1] * other[1]
    lengths = math.hypot(*main) * math.hypot(*other)
    assert math.degrees(math.acos(dot / lengths)) == pytest.approx(insert_angle)


def test_cutting_insert_nose_radius_changes_rendered_corner_geometry():
    small_radius, _depth, _key = display_tool_geometry({"type": "od_80", "noseRadius": 0.2, "tipOrientation": 3}, 50.0)
    rounded, _depth, _key = display_tool_geometry({"type": "od_80", "noseRadius": 0.8, "tipOrientation": 3}, 50.0)
    assert len(small_radius) > 4
    assert len(rounded) > 4
    assert rounded != small_radius


@pytest.mark.parametrize(
    "tool_spec",
    [
        {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3},
        {"type": "od_35", "noseRadius": 0.4, "tipOrientation": 3},
        {"type": "id_80", "noseRadius": 0.4, "tipOrientation": 2},
        {"type": "id_35", "noseRadius": 0.4, "tipOrientation": 2},
        {"type": "od_groove", "width": 4.0, "tipOrientation": 3},
        {"type": "od_groove", "width": 4.0, "tipOrientation": 4},
        {"type": "id_groove", "width": 4.0, "tipOrientation": 1},
        {"type": "id_groove", "width": 4.0, "tipOrientation": 2},
    ],
)
def test_supported_tool_display_and_stock_use_same_polygon(tool_spec):
    display_points, _depth, _key = display_tool_geometry(tool_spec, 50.0)
    stock_points = turning_tool_polygon(tool_spec, 50.0, stock_scope=True)

    assert stock_points is not None
    assert display_points == stock_points


def test_cutting_insert_nose_radius_changes_stock_envelope():
    motion = TraceMotion(1, 40.0, -5.0, 40.0, -10.0, tool="T0101", x_scale=0.5, spindle_running=True)
    spec = TurningStockSpec(outer_diameter=50, length=20, resolution=1)
    small = TurningStockTimeline((motion,), spec, {"T0101": {"type": "od_80", "noseRadius": 0.2, "tipOrientation": 3}})
    large = TurningStockTimeline((motion,), spec, {"T0101": {"type": "od_80", "noseRadius": 2.0, "tipOrientation": 3}})
    small.set_motion_count(1)
    large.set_motion_count(1)
    assert small.outer[_at(small, -10)] == pytest.approx(20.2)
    assert large.outer[_at(large, -10)] == pytest.approx(22.0)


def test_od_p3_insert_geometry_changes_stock_for_80_and_35_degree_tools():
    motion = TraceMotion(1, 50.0, -5.0, 30.0, -15.0, tool="T0101", x_scale=0.5, spindle_running=True)
    stock_spec = TurningStockSpec(outer_diameter=60, length=30, resolution=0.25)
    od80 = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}},
    )
    od35 = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0101": {"type": "od_35", "noseRadius": 0.4, "tipOrientation": 3}},
    )

    od80.set_motion_count(1)
    od35.set_motion_count(1)

    assert od80.outer[_at(od80, -10)] < od35.outer[_at(od35, -10)]
    assert od80.outer[_at(od80, -10)] < 18.0
    assert od35.outer[_at(od35, -10)] > 19.0


def test_id_p2_insert_geometry_changes_stock_for_80_and_35_degree_tools():
    motion = TraceMotion(1, 20.0, -5.0, 40.0, -15.0, tool="T0202", x_scale=0.5, spindle_running=True)
    stock_spec = TurningStockSpec(outer_diameter=60, inner_diameter=10, length=30, resolution=0.25)
    id80 = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0202": {"type": "id_80", "noseRadius": 0.4, "tipOrientation": 2}},
    )
    id35 = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0202": {"type": "id_35", "noseRadius": 0.4, "tipOrientation": 2}},
    )

    id80.set_motion_count(1)
    id35.set_motion_count(1)

    assert id80.inner[_at(id80, -10)] > id35.inner[_at(id35, -10)]
    assert id80.inner[_at(id80, -10)] > 17.0
    assert id35.inner[_at(id35, -10)] < 16.0


@pytest.mark.parametrize(
    ("tool_type", "start_x", "end_x", "inner_diameter", "profile_name"),
    [
        ("od_groove", 50.0, 30.0, 0.0, "outer"),
        ("id_groove", 20.0, 30.0, 20.0, "inner"),
    ],
)
def test_groove_width_is_swept_along_diagonal_trace(tool_type, start_x, end_x, inner_diameter, profile_name):
    motion = TraceMotion(1, start_x, -5.0, end_x, -15.0, tool="T0303", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(
            outer_diameter=50,
            inner_diameter=inner_diameter,
            length=25,
            resolution=0.5,
        ),
        {"T0303": {"type": tool_type, "width": 4.0}},
    )

    stock.set_motion_count(1)
    profile = getattr(stock, profile_name)
    middle = profile[_at(stock, -10)]
    endpoint = profile[_at(stock, -15)]

    if profile_name == "outer":
        assert endpoint == pytest.approx(15.0)
        assert 15.0 < middle < 20.0
    else:
        assert endpoint == pytest.approx(15.0)
        assert 10.0 < middle < 15.0


def test_unknown_turning_tool_does_not_remove_stock():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool="T9999", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {},
    )

    stock.set_motion_count(1)

    assert stock.inner == stock.initial_inner
    assert stock.outer == stock.initial_outer


@pytest.mark.parametrize(
    ("tool_type", "orientation", "cut_z", "clear_z", "profile_name", "inner_diameter"),
    [
        ("od_groove", 3, -6.0, -11.0, "outer", 0.0),
        ("od_groove", 4, -14.0, -6.0, "outer", 0.0),
        ("id_groove", 2, -7.0, -11.0, "inner", 20.0),
        ("id_groove", 1, -13.0, -7.0, "inner", 20.0),
    ],
)
def test_groove_tip_orientation_uses_edge_reference(
    tool_type,
    orientation,
    cut_z,
    clear_z,
    profile_name,
    inner_diameter,
):
    start_x = 50.0 if tool_type == "od_groove" else 20.0
    end_x = 30.0
    motion = TraceMotion(1, start_x, -10.0, end_x, -10.0, tool="T0303", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, inner_diameter=inner_diameter, length=25, resolution=1),
        {"T0303": {"type": tool_type, "width": 4.0, "tipOrientation": orientation}},
    )

    stock.set_motion_count(1)

    profile = getattr(stock, profile_name)
    if profile_name == "outer":
        assert profile[_at(stock, cut_z)] == pytest.approx(15.0)
        assert profile[_at(stock, clear_z)] == pytest.approx(25.0)
    else:
        assert profile[_at(stock, cut_z)] == pytest.approx(15.0)
        assert profile[_at(stock, clear_z)] == pytest.approx(10.0)


@pytest.mark.parametrize(
    ("tool_type", "expected_z"),
    [("od_groove", (0.0, 4.0)), ("id_groove", (0.0, 4.0))],
)
def test_legacy_groove_orientation_defaults_to_supported_edge(tool_type, expected_z):
    polygon = turning_tool_polygon({"type": tool_type, "width": 4.0}, 50.0, stock_scope=True)

    assert polygon is not None
    assert (min(point[1] for point in polygon), max(point[1] for point in polygon)) == pytest.approx(expected_z)


def test_stock_rewind_and_forward_replay_are_identical():
    motions = (
        TraceMotion(1, 50.0, -5.0, 30.0, -15.0, tool="T0101", x_scale=0.5),
        TraceMotion(1, 30.0, -15.0, 42.0, -20.0, tool="T0101", x_scale=0.5),
    )
    stock = TurningStockTimeline(
        motions,
        TurningStockSpec(outer_diameter=60, length=30, resolution=0.5),
        {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}},
    )

    stock.set_motion_count(2)
    first_outer = list(stock.outer)
    first_inner = list(stock.inner)
    stock.set_motion_count(0)
    assert stock.outer == stock.initial_outer
    assert stock.inner == stock.initial_inner
    stock.set_motion_count(2)
    assert stock.outer == first_outer
    assert stock.inner == first_inner


def test_stopped_spindle_still_removes_stock_geometrically():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool="T0101", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.outer[_at(stock, -10)] == pytest.approx(20.0, abs=0.5)


def test_radial_od_groove_records_exact_vertical_stock_walls():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=0.5),
        {"T0404": {"type": "od_groove", "width": 4.0, "tipOrientation": 3}},
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
        {"T0404": {"type": "od_groove", "width": 4.0, "tipOrientation": 3}},
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


def test_linear_stock_sweep_does_not_use_intermediate_motion_sampling(monkeypatch):
    def fail_sample(*_args, **_kwargs):
        raise AssertionError("linear stock sweep must not sample intermediate tool positions")

    monkeypatch.setattr("app.gcode.stock.sample_motion", fail_sample)
    motion = TraceMotion(1, 50.0, -5.0, 30.0, -35.0, tool="T0101", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=60, length=50, resolution=0.1),
        {"T0101": {"type": "od_80", "noseRadius": 0.4, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.outer[_at(stock, -20.0)] < stock.initial_outer[_at(stock, -20.0)]


def test_profile_break_cache_tracks_rewind_and_replay():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=0.5),
        {"T0404": {"type": "od_groove", "width": 4.0, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)
    expected = stock.profile_breaks
    stock.set_motion_count(0)
    assert stock.profile_breaks == ()
    stock.set_motion_count(1)
    assert stock.profile_breaks == expected
