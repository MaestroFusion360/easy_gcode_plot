"""Turning insert polygon geometry shared by preview and stock removal."""

import math

import pytest

from app.gcode.turning_tool_geometry import (
    THREAD_INSERT_OUTLINE,
    cutting_insert_points,
    display_tool_geometry,
    lathe_view_point,
    turning_tool_polygon,
)


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
    if tool_spec["type"] == "thread":
        assert display_points != stock_points
    else:
        assert display_points == stock_points


@pytest.mark.parametrize("parameter", [{"threadAngle": 55.0}, {"threadCornerRadius": 0.3}, {"threadTipWidth": 2.0}])
def test_thread_profile_parameters_do_not_change_display_geometry(parameter):
    base = {"type": "thread", "insertLength": 12.0, "tipOrientation": 8}
    assert display_tool_geometry(base, 50.0) == display_tool_geometry({**base, **parameter}, 50.0)


@pytest.mark.parametrize("orientation", [6, 8])
def test_thread_display_scales_uniformly_by_diameter(orientation):
    base = {"type": "thread", "insertLength": 12.0, "tipOrientation": orientation}
    original, depth, key = display_tool_geometry(base, 50.0)
    scaled, scaled_depth, scaled_key = display_tool_geometry({**base, "insertLength": 20.0}, 50.0)
    for actual, (x, z) in zip(scaled, original, strict=True):
        assert actual == pytest.approx((x * 20.0 / 12.0, z * 20.0 / 12.0))
    assert scaled_depth == pytest.approx(depth * 20.0 / 12.0)
    assert scaled_key != key


@pytest.mark.parametrize(("orientation", "direction"), [(8, 1), (6, -1)])
def test_thread_display_vertex_points_down_for_external_up_for_internal(orientation, direction):
    polygon = turning_tool_polygon({"type": "thread", "tipOrientation": orientation}, 50.0)
    assert polygon is not None
    assert polygon[2] == (0.0, 0.0)
    assert all(direction * x >= -1e-9 for x, _z in polygon)


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


@pytest.mark.parametrize(("orientation", "body_sign"), [(8, 1), (6, -1)])
def test_thread_orientation_is_radial_and_axially_symmetric(orientation, body_sign):
    spec = {"type": "thread", "tipOrientation": orientation, "threadCornerRadius": 0.0}
    polygon = turning_tool_polygon(spec, 50.0, stock_scope=True)
    assert polygon is not None
    assert all(body_sign * x >= -1e-9 for x, _z in polygon)
    assert max(z for _x, z in polygon) == pytest.approx(-min(z for _x, z in polygon))
    assert display_tool_geometry(spec, 50.0)[0] != polygon


def test_thread_missing_orientation_matches_explicit_p8():
    spec = {"type": "thread"}
    assert turning_tool_polygon(spec, 50.0) == turning_tool_polygon({**spec, "tipOrientation": 8}, 50.0)
    assert display_tool_geometry(spec, 50.0) == display_tool_geometry({**spec, "tipOrientation": 8}, 50.0)


@pytest.mark.parametrize("angle", [55.0, 60.0])
def test_thread_insert_has_three_small_profile_teeth(angle):
    polygon = turning_tool_polygon(
        {"type": "thread", "tipOrientation": 8, "threadAngle": angle, "threadCornerRadius": 0.0}, 50.0
    )
    assert polygon is not None
    assert len(polygon) == 15
    for index in (2, 7, 12):
        tip = polygon[index]
        before = polygon[index - 1]
        after = polygon[index + 1]
        a = (before[0] - tip[0], before[1] - tip[1])
        b = (after[0] - tip[0], after[1] - tip[1])
        cosine = sum(x * y for x, y in zip(a, b, strict=True)) / (math.hypot(*a) * math.hypot(*b))
        assert math.degrees(math.acos(cosine)) == pytest.approx(60.0)
    assert polygon[2] == pytest.approx((0.0, 0.0))


def test_thread_schematic_matches_supplied_dxf_and_mirrors_for_internal():
    external = turning_tool_polygon({"type": "thread", "tipOrientation": 8, "threadCornerRadius": 0.0}, 50.0)
    internal = turning_tool_polygon({"type": "thread", "tipOrientation": 6, "threadCornerRadius": 0.0}, 50.0)
    assert external is not None and internal is not None
    trace_x, trace_y = THREAD_INSERT_OUTLINE[2]
    for actual, (x, y) in zip(external, THREAD_INSERT_OUTLINE, strict=True):
        assert actual == pytest.approx((trace_y - y, x - trace_x))
    for actual, (x, z) in zip(internal, external, strict=True):
        assert actual == pytest.approx((-x, z))
