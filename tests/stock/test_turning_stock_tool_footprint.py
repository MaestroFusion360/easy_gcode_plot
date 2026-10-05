"""How turning tool geometry changes the removed stock envelope."""

import pytest

from app.gcode.kernel import TraceMotion
from app.gcode.program_execution import execute_program
from app.gcode.stock import TurningStockSpec, TurningStockTimeline


def _at(timeline, z_value):
    return min(range(len(timeline.z)), key=lambda index: abs(timeline.z[index] - z_value))


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
    assert small.outer[_at(small, -9)] == pytest.approx(20.0)
    assert large.outer[_at(large, -9)] == pytest.approx(20.27642884587624)
    # At the rounded tip's tangent Z slice, the footprint has zero area.
    assert small.material_intervals[_at(small, -10)] == ((0.0, 25.0),)
    assert large.material_intervals[_at(large, -10)] == ((0.0, 25.0),)


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


@pytest.mark.parametrize("applications", [[], ["od"], ["id"], ["od", "id"]])
def test_g71_boring_with_p2_preserves_outer_wall_and_replays(fixture_text, applications):
    tool = {
        "type": "diamond_80",
        "applications": ["id"],
        "noseRadius": 0.4,
        "tipOrientation": 2,
        "insertLength": 9.0,
    }
    result, tools, _ = execute_program(
        fixture_text("turning/lathe_cycles_example.nc"),
        language="fanuc_turn",
        current_tools={"T0303": tool},
    )
    assert result.ok and result.complete, result.diagnostics
    tools["T0303"]["applications"] = applications
    stock = TurningStockTimeline(result.motions, TurningStockSpec(outer_diameter=124, length=65, resolution=0.5), tools)
    first = next(index for index, motion in enumerate(result.motions) if motion.tool == "T0303" and motion.move == 1)
    last = max(index for index, motion in enumerate(result.motions) if motion.tool == "T0303") + 1
    stock.set_motion_count(first)
    before_outer = list(stock.outer)
    before_inner = list(stock.inner)
    before_intervals = list(stock.material_intervals)
    stock.set_motion_count(first + 1)
    assert stock.outer == before_outer
    assert stock.inner[_at(stock, -20)] > before_inner[_at(stock, -20)]
    stock.set_motion_count(last)
    assert stock.outer == before_outer
    assert stock.inner[_at(stock, -5)] == pytest.approx(28.011)
    assert stock.inner[_at(stock, -40)] > 15
    after_inner = list(stock.inner)
    after_intervals = list(stock.material_intervals)
    stock.set_motion_count(first)
    assert stock.inner == before_inner
    assert stock.outer == before_outer
    assert stock.material_intervals == before_intervals
    stock.set_motion_count(last)
    assert stock.inner == after_inner
    assert stock.outer == before_outer
    assert stock.material_intervals == after_intervals


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "diamond_80", "tipOrientation": 2, "noseRadius": 0.4, "insertLength": 9},
        {"type": "diamond_35", "tipOrientation": 6, "noseRadius": 0.4},
        {"type": "square", "tipOrientation": 2, "noseRadius": 0.4},
        {"type": "triangle", "tipOrientation": 3, "noseRadius": 0.4},
        {"type": "round", "tipOrientation": 7, "insertLength": 8},
        {"type": "groove", "tipOrientation": 2, "width": 3, "grooveCuttingPlane": "radial"},
        {"type": "groove", "tipOrientation": 3, "width": 3, "grooveCuttingPlane": "face"},
        {"type": "thread", "tipOrientation": 6, "insertLength": 12, "threadAngle": 60},
        {"type": "thread", "tipOrientation": 8, "insertLength": 12, "threadAngle": 60},
    ],
)
def test_stock_is_identical_for_all_ui_application_filters(geometry):
    motion = TraceMotion(1, 40, 2, 40, -12, tool="T0101", feed=2, x_scale=0.5, threading=True)
    spec = TurningStockSpec(outer_diameter=60, inner_diameter=10, length=20, resolution=0.25)
    snapshots = []
    for applications in ([], ["od"], ["id"], ["face"], ["od", "id"], ["od", "id", "face"]):
        stock = TurningStockTimeline((motion,), spec, {"T0101": {**geometry, "applications": applications}})
        stock.set_motion_count(1)
        snapshots.append((stock.inner, stock.outer, stock.material_intervals, stock.profile_breaks))
    assert all(snapshot == snapshots[0] for snapshot in snapshots)
