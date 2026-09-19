import math

import pytest

from app.gcode.kernel import TraceMotion, execute
from app.gcode.kernel.api_types import ArcGeometry
from app.gcode.turning_stock_bounds import auto_turning_stock_suggestion


def test_auto_stock_uses_cutting_motions_and_ignores_rapid_outliers():
    result = execute("G21 G18 G90\nG0 X200 Z50\nG0 X40 Z0\nG1 X40 Z-25 F100\nG0 X180 Z100\nM30")

    suggestion = auto_turning_stock_suggestion(result.motions)

    assert suggestion is not None
    assert suggestion.outer_diameter == pytest.approx(40.0)
    assert suggestion.inner_diameter == pytest.approx(0.0)
    assert suggestion.length == pytest.approx(25.0)
    assert suggestion.front_z == pytest.approx(0.0)


def test_auto_stock_returns_none_without_cutting_motions():
    result = execute("G21 G18 G90\nG0 X200 Z50\nM30")

    assert auto_turning_stock_suggestion(result.motions) is None


def test_auto_stock_uses_exact_g18_arc_extrema():
    motion = TraceMotion(
        3,
        20.0,
        0.0,
        20.0,
        -20.0,
        x_scale=0.5,
        arc=ArcGeometry((10.0, 0.0, -10.0), 10.0, math.pi, 18, clockwise=True, full_circle=False),
    )

    suggestion = auto_turning_stock_suggestion((motion,))

    assert suggestion is not None
    assert suggestion.outer_diameter == pytest.approx(40.0)
    assert suggestion.length == pytest.approx(20.0)


def test_auto_stock_preserves_positive_z_work_offset():
    result = execute("G21 G18 G90\nG0 X160 Z180\nG1 X140 Z180 F100\nG1 X100 Z100\nG1 X40 Z40\nM30")

    suggestion = auto_turning_stock_suggestion(result.motions)

    assert suggestion is not None
    assert suggestion.outer_diameter == pytest.approx(160.0)
    assert suggestion.length == pytest.approx(140.0)
    assert suggestion.front_z == pytest.approx(180.0)
