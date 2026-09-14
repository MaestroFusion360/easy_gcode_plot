"""Regression tests for axisymmetric turning Stock Removal."""

import math

import pytest

from app.gcode.kernel import TraceMotion, execute
from app.gcode.stock import TurningStockSpec, TurningStockTimeline, profile_interval_mesh_spans
from app.gcode.turning_tool_geometry import (
    cutting_insert_points,
    display_tool_geometry,
    lathe_view_point,
    turning_tool_polygon,
)
from app.ui.stock_overlay import material_interval_mesh_spans


def _at(timeline, z_value):
    return min(range(len(timeline.z)), key=lambda index: abs(timeline.z[index] - z_value))


def test_od_cut_reduces_outer_profile_and_rewinds():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool="T0101", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
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
        {"T0202": {"type": "diamond_80", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2}},
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


def test_groove_width_removes_outer_material_and_rewinds():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0404": {"type": "groove", "applications": ["od"], "width": 4.0}},
    )
    stock.set_motion_count(1)
    assert stock.outer[_at(stock, -10)] == pytest.approx(15.0)
    assert stock.outer[_at(stock, -6)] == pytest.approx(15.0)
    assert stock.outer[_at(stock, -11)] == pytest.approx(25.0)
    stock.set_motion_count(0)
    assert stock.outer == stock.initial_outer


def test_groove_width_removes_inner_material():
    motion = TraceMotion(1, 20.0, -10.0, 30.0, -10.0, tool="T0505", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, inner_diameter=20, length=40, resolution=1),
        {
            "T0505": {
                "type": "groove",
                "applications": ["id"],
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
    ("tool_type", "insert_angle", "edge_angle", "orientation", "internal", "radial_sign"),
    [
        ("diamond_80", 80.0, 5.0, 3, False, 1.0),
        ("diamond_80", 80.0, 5.0, 2, True, -1.0),
        ("diamond_35", 35.0, 3.0, 3, False, 1.0),
        ("diamond_35", 35.0, 3.0, 2, True, -1.0),
    ],
)
def test_cutting_insert_has_fixed_angle_and_main_edge_at_tip(
    tool_type, insert_angle, edge_angle, orientation, internal, radial_sign
):
    points = cutting_insert_points(
        4.0,
        insert_angle,
        edge_angle,
        orientation,
        internal=internal,
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


def test_triangle_insert_is_equilateral_instead_of_a_sixty_degree_rhombus():
    points = turning_tool_polygon(
        {"type": "triangle", "noseRadius": 0.0, "tipOrientation": 3, "insertLength": 12.0},
        50.0,
    )

    assert points is not None
    assert len(points) == 3
    side_lengths = [
        math.hypot(
            points[(index + 1) % 3][0] - points[index][0],
            points[(index + 1) % 3][1] - points[index][1],
        )
        for index in range(3)
    ]
    assert side_lengths == pytest.approx([12.0, 12.0, 12.0])


def test_round_insert_uses_insert_diameter_for_trace_point_position():
    spec = {"type": "round", "noseRadius": 0.4, "tipOrientation": 3, "insertLength": 12.0}
    points = turning_tool_polygon(spec, 50.0)

    assert points is not None
    center_x = sum(x_value for x_value, _z in points) / len(points)
    center_z = sum(z_value for _x, z_value in points) / len(points)
    assert math.hypot(center_x, center_z) == pytest.approx(6.0)
    assert all(math.hypot(x_value - center_x, z_value - center_z) == pytest.approx(6.0) for x_value, z_value in points)

    changed_nose = turning_tool_polygon({**spec, "noseRadius": 3.0}, 50.0)
    assert changed_nose is not None
    for actual, expected in zip(changed_nose, points, strict=True):
        assert actual == pytest.approx(expected)


def test_cutting_insert_nose_radius_changes_rendered_corner_geometry():
    small_radius, _depth, _key = display_tool_geometry(
        {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.2, "tipOrientation": 3}, 50.0
    )
    rounded, _depth, _key = display_tool_geometry(
        {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.8, "tipOrientation": 3}, 50.0
    )
    assert len(small_radius) > 4
    assert len(rounded) > 4
    assert rounded != small_radius


@pytest.mark.parametrize(
    "tool_type",
    ["diamond_80", "diamond_35", "diamond_80", "diamond_35"],
)
def test_each_insert_family_has_eight_distinct_rigid_plate_rotations(tool_type):
    polygons = [
        turning_tool_polygon({"type": tool_type, "noseRadius": 0.4, "tipOrientation": orientation}, 50.0)
        for orientation in range(1, 9)
    ]
    assert all(polygon is not None for polygon in polygons)
    signatures = {tuple((round(x, 8), round(z, 8)) for x, z in polygon) for polygon in polygons}
    assert len(signatures) == 8

    radial_signatures = [sorted(round(math.hypot(x, z), 8) for x, z in polygon) for polygon in polygons]
    assert all(signature == radial_signatures[0] for signature in radial_signatures[1:])


@pytest.mark.parametrize("tool_type", ["diamond_80", "diamond_35", "diamond_80", "diamond_35"])
@pytest.mark.parametrize("orientation", range(1, 10))
def test_all_insert_families_have_nine_deterministic_preview_polygons(tool_type, orientation):
    points, _depth, _key = display_tool_geometry(
        {"type": tool_type, "noseRadius": 0.4, "tipOrientation": orientation},
        50.0,
    )
    assert all(math.isfinite(value) for point in points for value in point)


@pytest.mark.parametrize("tool_type", ["diamond_80", "diamond_35", "diamond_80", "diamond_35", "square", "triangle"])
@pytest.mark.parametrize("orientation", [1, 2, 3, 4, 6, 7])
def test_auto_insert_orientations_share_geometry_between_preview_and_stock(tool_type, orientation):
    spec = {"type": tool_type, "noseRadius": 0.4, "tipOrientation": orientation, "insertLength": 12.0}

    preview = turning_tool_polygon(spec, 50.0)
    stock = turning_tool_polygon(spec, 50.0, stock_scope=True)

    assert preview is not None
    assert stock == preview


@pytest.mark.parametrize("tool_type", ["diamond_80", "diamond_35"])
@pytest.mark.parametrize("application", ["od", "id"])
def test_p6_and_p8_rotate_the_entire_insert_by_180_degrees(tool_type, application):
    common = {"type": tool_type, "applications": [application], "noseRadius": 0.4}
    p6 = turning_tool_polygon({**common, "tipOrientation": 6}, 50.0)
    p8 = turning_tool_polygon({**common, "tipOrientation": 8}, 50.0)
    assert p6 is not None and p8 is not None
    for actual, expected in zip(p8, p6, strict=True):
        assert actual == pytest.approx((-expected[0], -expected[1]))


def test_lathe_preview_projection_matches_stock_removal_camera_axes():
    assert lathe_view_point(1.0, 0.0) == (0.0, -1.0)
    assert lathe_view_point(0.0, 1.0) == (1.0, 0.0)


@pytest.mark.parametrize(
    "tool_spec",
    [
        {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3},
        {"type": "diamond_35", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3},
        {"type": "diamond_80", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2},
        {"type": "diamond_35", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2},
        {"type": "groove", "applications": ["od"], "width": 4.0, "tipOrientation": 3},
        {"type": "groove", "applications": ["od"], "width": 4.0, "tipOrientation": 4},
        {"type": "groove", "applications": ["id"], "width": 4.0, "tipOrientation": 1},
        {"type": "groove", "applications": ["id"], "width": 4.0, "tipOrientation": 2},
        {"type": "square", "noseRadius": 0.4, "tipOrientation": 3},
        {"type": "round", "noseRadius": 3.0, "tipOrientation": 3},
        {"type": "triangle", "noseRadius": 0.4, "tipOrientation": 3},
        {
            "type": "thread",
            "insertLength": 12.0,
            "threadAngle": 60.0,
            "threadTipWidth": 0.8,
            "threadCornerRadius": 0.1,
            "tipOrientation": 3,
        },
    ],
)
def test_supported_tool_display_and_stock_use_same_polygon(tool_spec):
    display_points, _depth, _key = display_tool_geometry(tool_spec, 50.0)
    stock_points = turning_tool_polygon(tool_spec, 50.0, stock_scope=True)

    assert stock_points is not None
    assert display_points == stock_points


def test_thread_parameters_change_tool_geometry_and_cache_key():
    base = {
        "type": "thread",
        "insertLength": 12.0,
        "threadAngle": 60.0,
        "threadTipWidth": 0.8,
        "threadCornerRadius": 0.1,
        "tipOrientation": 3,
    }
    base_points, _depth, base_key = display_tool_geometry(base, 50.0)
    changed_points, _depth, changed_key = display_tool_geometry({**base, "threadAngle": 55.0}, 50.0)
    rounded_points, _depth, rounded_key = display_tool_geometry({**base, "threadCornerRadius": 0.3}, 50.0)

    assert base_points != changed_points
    assert base_key != changed_key
    assert base_points != rounded_points
    assert base_key != rounded_key
    assert turning_tool_polygon(base, 50.0, stock_scope=True) == base_points


def test_cutting_insert_nose_radius_changes_stock_envelope():
    motion = TraceMotion(1, 40.0, -5.0, 40.0, -10.0, tool="T0101", x_scale=0.5, spindle_running=True)
    spec = TurningStockSpec(outer_diameter=50, length=20, resolution=1)
    small = TurningStockTimeline(
        (motion,),
        spec,
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.2, "tipOrientation": 3}},
    )
    large = TurningStockTimeline(
        (motion,),
        spec,
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 2.0, "tipOrientation": 3}},
    )
    small.set_motion_count(1)
    large.set_motion_count(1)
    assert small.outer[_at(small, -10)] == pytest.approx(20.2)
    assert large.outer[_at(large, -10)] == pytest.approx(22.0)


def test_diamond_geometry_changes_stock_for_od_application():
    motion = TraceMotion(1, 50.0, -5.0, 30.0, -15.0, tool="T0101", x_scale=0.5, spindle_running=True)
    stock_spec = TurningStockSpec(outer_diameter=60, length=30, resolution=0.25)
    diamond_80_od = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
    )
    diamond_35_od = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0101": {"type": "diamond_35", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
    )

    diamond_80_od.set_motion_count(1)
    diamond_35_od.set_motion_count(1)

    assert diamond_80_od.outer[_at(diamond_80_od, -10)] < diamond_35_od.outer[_at(diamond_35_od, -10)]
    assert diamond_80_od.outer[_at(diamond_80_od, -10)] < 18.0
    assert diamond_35_od.outer[_at(diamond_35_od, -10)] > 19.0


def test_diamond_geometry_changes_stock_for_id_application():
    motion = TraceMotion(1, 20.0, -5.0, 40.0, -15.0, tool="T0202", x_scale=0.5, spindle_running=True)
    stock_spec = TurningStockSpec(outer_diameter=60, inner_diameter=10, length=30, resolution=0.25)
    diamond_80_id = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0202": {"type": "diamond_80", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2}},
    )
    diamond_35_id = TurningStockTimeline(
        (motion,),
        stock_spec,
        {"T0202": {"type": "diamond_35", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2}},
    )

    diamond_80_id.set_motion_count(1)
    diamond_35_id.set_motion_count(1)

    assert diamond_80_id.inner[_at(diamond_80_id, -10)] > diamond_35_id.inner[_at(diamond_35_id, -10)]
    assert diamond_80_id.inner[_at(diamond_80_id, -10)] > 17.0
    assert diamond_35_id.inner[_at(diamond_35_id, -10)] < 16.0


@pytest.mark.parametrize(
    ("tool_type", "application", "start_x", "end_x", "inner_diameter", "profile_name"),
    [
        ("groove", "od", 50.0, 30.0, 0.0, "outer"),
        ("groove", "id", 20.0, 30.0, 20.0, "inner"),
    ],
)
def test_groove_width_is_swept_along_diagonal_trace(
    tool_type, application, start_x, end_x, inner_diameter, profile_name
):
    motion = TraceMotion(1, start_x, -5.0, end_x, -15.0, tool="T0303", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(
            outer_diameter=50,
            inner_diameter=inner_diameter,
            length=25,
            resolution=0.5,
        ),
        {"T0303": {"type": tool_type, "applications": [application], "width": 4.0}},
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


def test_missing_turning_tool_uses_default_diamond_80_od_application():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool=None, x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {},
    )

    stock.set_motion_count(1)

    assert stock.outer != stock.initial_outer


def test_turning_tap_uses_drilling_stock_footprint():
    motion = TraceMotion(1, 0.0, 0.0, 0.0, -20.0, tool="T0101", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0101": {"type": "tap", "diameter": 10.0, "length": 40.0, "tipAngle": 60.0}},
    )

    stock.set_motion_count(1)

    assert max(stock.inner) == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("tool_type", "application", "orientation", "cut_z", "clear_z", "profile_name", "inner_diameter"),
    [
        ("groove", "od", 3, -6.0, -11.0, "outer", 0.0),
        ("groove", "od", 4, -14.0, -6.0, "outer", 0.0),
        ("groove", "id", 2, -7.0, -11.0, "inner", 20.0),
        ("groove", "id", 1, -13.0, -7.0, "inner", 20.0),
    ],
)
def test_groove_tip_orientation_uses_edge_reference(
    tool_type,
    application,
    orientation,
    cut_z,
    clear_z,
    profile_name,
    inner_diameter,
):
    start_x = 50.0 if application == "od" else 20.0
    end_x = 30.0
    motion = TraceMotion(1, start_x, -10.0, end_x, -10.0, tool="T0303", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, inner_diameter=inner_diameter, length=25, resolution=1),
        {
            "T0303": {
                "type": tool_type,
                "applications": [application],
                "width": 4.0,
                "tipOrientation": orientation,
            }
        },
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
    ("application", "expected_z"),
    [("od", (0.0, 4.0)), ("id", (0.0, 4.0))],
)
def test_groove_missing_orientation_defaults_to_supported_edge(application, expected_z):
    polygon = turning_tool_polygon(
        {"type": "groove", "applications": [application], "width": 4.0},
        50.0,
        stock_scope=True,
    )

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
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
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
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.outer[_at(stock, -10)] == pytest.approx(20.0, abs=0.5)


def test_radial_groove_records_exact_vertical_stock_walls():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=0.5),
        {"T0404": {"type": "groove", "applications": ["od"], "width": 4.0, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.profile_breaks == pytest.approx((-10.0, -6.0))


def test_facing_pass_crossing_center_removes_front_stock_to_a_flat_z_wall():
    motions = (
        TraceMotion(1, 24.8, 0.0, 24.0, 0.0, tool="T0808", x_scale=0.5),
        TraceMotion(1, 24.0, 0.0, -0.8, 0.0, tool="T0808", x_scale=0.5),
        TraceMotion(1, -0.8, 0.0, -0.8, 0.4, tool="T0808", x_scale=0.5),
    )
    stock = TurningStockTimeline(
        motions,
        TurningStockSpec(outer_diameter=24.8, length=12.0, resolution=0.05, front_z=2.0),
        {
            "T0808": {
                "type": "diamond_80",
                "applications": ["od"],
                "noseRadius": 0.4,
                "tipOrientation": 3,
                "insertLength": 12.0,
            }
        },
    )

    stock.set_motion_count(len(motions))

    assert stock.profile_breaks[0] == pytest.approx(0.0)
    assert stock.outer[_at(stock, -0.05)] == pytest.approx(12.4)
    for z_value in (0.0, 0.05, 0.4, 1.0, 2.0):
        assert stock.material_intervals[_at(stock, z_value)] == ()


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


def test_linear_stock_sweep_does_not_use_intermediate_motion_sampling(monkeypatch):
    def fail_sample(*_args, **_kwargs):
        raise AssertionError("linear stock sweep must not sample intermediate tool positions")

    monkeypatch.setattr("app.gcode.stock.sample_motion", fail_sample)
    motion = TraceMotion(1, 50.0, -5.0, 30.0, -35.0, tool="T0101", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=60, length=50, resolution=0.1),
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.outer[_at(stock, -20.0)] < stock.initial_outer[_at(stock, -20.0)]


def test_profile_break_cache_tracks_rewind_and_replay():
    motion = TraceMotion(1, 50.0, -10.0, 30.0, -10.0, tool="T0404", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=0.5),
        {"T0404": {"type": "groove", "applications": ["od"], "width": 4.0, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)
    expected = stock.profile_breaks
    stock.set_motion_count(0)
    assert stock.profile_breaks == ()
    stock.set_motion_count(1)
    assert stock.profile_breaks == expected


@pytest.mark.parametrize("orientation", [2, 3])
def test_groove_removes_only_local_radial_footprint_and_rewinds(orientation):
    motion = TraceMotion(1, 40.0, -2.0, 40.0, -10.0, tool="T0202", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=60, inner_diameter=10, length=20, resolution=0.5),
        {
            "T0202": {
                "type": "groove",
                "applications": ["face"],
                "width": 3.0,
                "noseRadius": 0.0,
                "tipOrientation": orientation,
            }
        },
    )

    stock.set_motion_count(1)
    intervals = stock.material_intervals[_at(stock, -8.0)]
    assert len(intervals) == 2
    assert intervals[0][0] == pytest.approx(5.0)
    assert intervals[-1][1] == pytest.approx(30.0)
    assert stock.inner[_at(stock, -8.0)] == pytest.approx(5.0)
    assert stock.outer[_at(stock, -8.0)] == pytest.approx(30.0)

    stock.set_motion_count(0)
    assert stock.material_intervals == stock.initial_material_intervals
    stock.set_motion_count(1)
    assert stock.material_intervals[_at(stock, -8.0)] == intervals


def test_groove_g74_cycle_cuts_only_feed_moves_and_keeps_local_material():
    source = """(AXIAL GROOVING)
N2 T0202
G18 G99
G96 S450 M03
G00 X50. Z5.
G74 R2.
G74 X30. Z-10. P3. Q3. F0.3
G28 U0. W0. M09 (HOME)
M05
"""
    result = execute(source, language="fanuc_turn")
    cycle = [motion for motion in result.motions if motion.source_kind == "cycle"]
    assert [(motion.move, motion.end_x, motion.end_z) for motion in cycle[:11]] == [
        (1, 50.0, 2.0),
        (0, 50.0, 4.0),
        (1, 50.0, -1.0),
        (0, 50.0, 1.0),
        (1, 50.0, -4.0),
        (0, 50.0, -2.0),
        (1, 50.0, -7.0),
        (0, 50.0, -5.0),
        (1, 50.0, -10.0),
        (0, 50.0, -8.0),
        (0, 50.0, 5.0),
    ]
    assert sorted({motion.end_x for motion in cycle if motion.move == 1}) == [30.0, 32.0, 38.0, 44.0, 50.0]

    tools = {
        "T0202": {"type": "groove", "applications": ["face"], "width": 3.0, "noseRadius": 0.0, "tipOrientation": 3}
    }
    stock = TurningStockTimeline(result.motions, TurningStockSpec(outer_diameter=60, length=30, resolution=0.5), tools)
    rapid_index = next(
        index for index, motion in enumerate(result.motions) if motion.source_kind == "cycle" and motion.move == 0
    )
    stock.set_motion_count(rapid_index)
    before_rapid = list(stock.material_intervals)
    stock.set_motion_count(rapid_index + 1)
    assert stock.material_intervals == before_rapid
    stock.set_motion_count(len(result.motions))
    assert any(len(intervals) > 1 for intervals in stock.material_intervals)


@pytest.mark.parametrize("tool_type,orientation", [("groove", 3), ("groove", 2), ("groove", 3)])
def test_groove_radius_changes_real_cutter_footprint(tool_type, orientation):
    sharp = turning_tool_polygon(
        {"type": tool_type, "width": 4.0, "noseRadius": 0.0, "tipOrientation": orientation}, 50.0
    )
    rounded = turning_tool_polygon(
        {"type": tool_type, "width": 4.0, "noseRadius": 0.4, "tipOrientation": orientation}, 50.0
    )
    assert sharp is not None and rounded is not None
    assert len(sharp) == 4
    assert len(rounded) > 4
    assert rounded != sharp


def test_interval_mesh_does_not_cross_connect_one_profile_to_two_rings():
    spans = material_interval_mesh_spans(((0.0, 30.0),), ((0.0, 17.0), (20.0, 30.0)))

    assert spans == ((0.0, 17.0, 0.0, 17.0), (20.0, 30.0, 20.0, 30.0))


def test_interval_mesh_preserves_sloped_profiles_when_topology_matches():
    spans = material_interval_mesh_spans(((2.0, 20.0), (24.0, 30.0)), ((3.0, 19.0), (23.0, 29.0)))

    assert spans == ((2.0, 20.0, 3.0, 19.0), (24.0, 30.0, 23.0, 29.0))


def test_interval_mesh_reaches_exact_face_break_when_next_slice_is_empty():
    spans = material_interval_mesh_spans(((0.0, 12.4),), (), end_break=True)

    assert spans == ((0.0, 12.4, 0.0, 12.4),)


@pytest.mark.parametrize(
    ("application", "thread_x", "initial_inner", "profile_name", "expected"),
    [
        ("od", 36.0, 0.0, "outer", (18.0, 18.0 + math.sqrt(3.0) * 0.5, 18.0 + math.sqrt(3.0))),
        ("id", 28.0, 20.0, "inner", (14.0, 14.0 - math.sqrt(3.0) * 0.5, 14.0 - math.sqrt(3.0))),
    ],
)
def test_threading_stock_removal_uses_pitch_and_insert_angle(
    application, thread_x, initial_inner, profile_name, expected
):
    motion = TraceMotion(
        1,
        thread_x,
        0.0,
        thread_x,
        -6.0,
        feed=2.0,
        tool="T0606",
        x_scale=0.5,
        spindle_running=True,
        threading=True,
    )
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, inner_diameter=initial_inner, length=8, resolution=0.25),
        {
            "T0606": {
                "type": "thread",
                "applications": [application],
                "tipOrientation": 8,
                "threadAngle": 60.0,
                "threadCornerRadius": 0.0,
            }
        },
    )

    stock.set_motion_count(1)

    profile = getattr(stock, profile_name)
    assert profile[_at(stock, 0.0)] == pytest.approx(expected[0])
    assert profile[_at(stock, -0.5)] == pytest.approx(expected[1])
    assert profile[_at(stock, -1.0)] == pytest.approx(expected[2])
    assert profile[_at(stock, -2.0)] == pytest.approx(expected[0])
    assert stock.profile_breaks == (-6.0, 0.0)


def test_thread_corner_radius_rounds_the_periodic_root():
    base = {
        "type": "thread",
        "applications": ["od"],
        "tipOrientation": 8,
        "threadAngle": 60.0,
    }
    motion = TraceMotion(
        1,
        36.0,
        0.0,
        36.0,
        -4.0,
        feed=2.0,
        tool="T0606",
        x_scale=0.5,
        threading=True,
    )
    sharp = TurningStockTimeline(
        (motion,), TurningStockSpec(outer_diameter=50, length=5, resolution=0.05), {"T0606": base}
    )
    rounded = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=5, resolution=0.05),
        {"T0606": {**base, "threadCornerRadius": 0.1}},
    )

    sharp.set_motion_count(1)
    rounded.set_motion_count(1)

    assert rounded.outer[_at(rounded, -0.05)] < sharp.outer[_at(sharp, -0.05)]
    assert rounded.outer[_at(rounded, 0.0)] == pytest.approx(18.0)


def test_thread_tool_infeed_and_retract_do_not_cut_with_the_full_insert_body():
    motions = (
        TraceMotion(1, 40.0, -1.25, 13.0, -1.25, tool="T0202", x_scale=0.5),
        TraceMotion(1, 13.0, -12.0, 40.0, -12.0, tool="T0202", x_scale=0.5),
    )
    stock = TurningStockTimeline(
        motions,
        TurningStockSpec(outer_diameter=50, length=20, resolution=0.25),
        {"T0202": {"type": "thread", "applications": ["od"], "tipOrientation": 8}},
    )

    stock.set_motion_count(2)

    assert stock.outer == stock.initial_outer
    assert stock.profile_breaks == ()


def _trace_direction_angle(points):
    center_x = (min(x for x, _z in points) + max(x for x, _z in points)) * 0.5
    center_z = (min(z for _x, z in points) + max(z for _x, z in points)) * 0.5
    screen_x, screen_y = lathe_view_point(-center_x, -center_z)
    return math.degrees(math.atan2(-screen_y, screen_x)) % 360.0


def test_diamond_35_od_p4_is_horizontal_mirror_of_p3():
    p3 = turning_tool_polygon(
        {"type": "diamond_35", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3, "insertLength": 16.0},
        50.0,
    )
    p4 = turning_tool_polygon(
        {"type": "diamond_35", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 4, "insertLength": 16.0},
        50.0,
    )

    assert p3 is not None and p4 is not None
    expected = sorted((round(x, 8), round(-z, 8)) for x, z in p3)
    actual = sorted((round(x, 8), round(z, 8)) for x, z in p4)
    assert actual == expected


def test_diamond_35_id_p1_is_horizontal_mirror_of_p2():
    p2 = turning_tool_polygon(
        {"type": "diamond_35", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 2, "insertLength": 16.0},
        50.0,
    )
    p1 = turning_tool_polygon(
        {"type": "diamond_35", "applications": ["id"], "noseRadius": 0.4, "tipOrientation": 1, "insertLength": 16.0},
        50.0,
    )

    assert p1 is not None and p2 is not None
    expected = sorted((round(x, 8), round(-z, 8)) for x, z in p2)
    actual = sorted((round(x, 8), round(z, 8)) for x, z in p1)
    assert actual == expected


@pytest.mark.parametrize(
    ("tool_type", "orientation", "expected_angle"),
    [("diamond_35", 7, 180.0), ("diamond_35", 6, 90.0), ("diamond_35", 7, 180.0)],
)
def test_diamond35_cardinal_auto_trace_directions_are_exact(tool_type, orientation, expected_angle):
    points = turning_tool_polygon(
        {"type": tool_type, "noseRadius": 0.4, "tipOrientation": orientation, "insertLength": 16.0}, 50.0
    )

    assert points is not None
    assert _trace_direction_angle(points) == pytest.approx(expected_angle)
