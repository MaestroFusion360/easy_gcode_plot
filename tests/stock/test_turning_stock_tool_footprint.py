"""How turning tool geometry changes the removed stock envelope."""

import pytest

from app.gcode.kernel import TraceMotion
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
