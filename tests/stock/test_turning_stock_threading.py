"""Turning thread stock removal geometry."""

import math

import pytest

from app.gcode.kernel import TraceMotion
from app.gcode.stock import TurningStockSpec, TurningStockTimeline


def _at(timeline, z_value):
    return min(range(len(timeline.z)), key=lambda index: abs(timeline.z[index] - z_value))


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
