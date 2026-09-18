"""Turning stock rewind, caching, and sweep behaviour."""

from app.gcode.kernel import TraceMotion, execute
from app.gcode.stock import TurningStockSpec, TurningStockTimeline


def _at(timeline, z_value):
    return min(range(len(timeline.z)), key=lambda index: abs(timeline.z[index] - z_value))


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
