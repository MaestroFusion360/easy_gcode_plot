"""Axisymmetric turning Stock Removal profile behaviour."""

import pytest

from app.gcode.kernel import TraceMotion
from app.gcode.stock import TurningStockSpec, TurningStockTimeline


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


def test_unknown_turning_tool_uses_default_geometry_to_remove_stock():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool="T9999", x_scale=0.5, spindle_running=True)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {},
    )

    stock.set_motion_count(1)

    assert stock.inner == stock.initial_inner
    assert any(current < initial for current, initial in zip(stock.outer, stock.initial_outer, strict=True))
    stock.set_motion_count(0)
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


def test_stopped_spindle_still_removes_stock_geometrically():
    motion = TraceMotion(1, 40.0, 0.0, 40.0, -20.0, tool="T0101", x_scale=0.5)
    stock = TurningStockTimeline(
        (motion,),
        TurningStockSpec(outer_diameter=50, length=40, resolution=1),
        {"T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.4, "tipOrientation": 3}},
    )

    stock.set_motion_count(1)

    assert stock.outer[_at(stock, -10)] == pytest.approx(20.0, abs=0.5)


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
