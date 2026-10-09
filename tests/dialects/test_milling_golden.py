"""Trace contracts for representative checked-in milling programs."""

from __future__ import annotations

import math

import pytest

from app.gcode.kernel import execute


@pytest.mark.parametrize(
    (
        "name",
        "kinematics",
        "motion_count",
        "cycle_count",
        "arc_count",
        "rotary_events",
        "end",
        "bounds",
        "diagnostics",
    ),
    [
        (
            "indexed_table_a.nc",
            "4ax_table_a",
            382,
            6,
            6,
            2,
            (444.0, 0.0, 500.0),
            (-12.0, 506.0, -86.909, 86.909, -500.0, 500.0),
            {"UNSUPPORTED_M_CODE", "UNVERIFIED_CUTTER_COMPENSATION"},
        ),
        (
            "indexed_table_b.nc",
            "4ax_table_b",
            2080,
            1393,
            103,
            25,
            (-475.5282581475768, -35.0, 154.5084971874736),
            (-500.51983158343245, 357.21787322572857, -84.0, 73.025, -500.0, 500.0),
            {"UNSUPPORTED_M_CODE", "UNVERIFIED_CUTTER_COMPENSATION"},
        ),
        (
            "indexed_table_c.nc",
            "4ax_table_c",
            797,
            0,
            10,
            765,
            (18.270943798452425, -55.08493359089937, 500.0),
            (-54.53, 54.53, -55.085, 54.53, -40.0, 500.0),
            set(),
        ),
        (
            "flange_plate_benchmark.nc",
            None,
            325,
            63,
            58,
            0,
            (0.0, 0.0, 0.0),
            (-85.0, 75.0, -55.0, 55.0, -18.0, 5.0),
            {"UNVERIFIED_CUTTER_COMPENSATION"},
        ),
    ],
)
def test_milling_fixture_trace_contract(
    name,
    kinematics,
    motion_count,
    cycle_count,
    arc_count,
    rotary_events,
    end,
    bounds,
    diagnostics,
    fixture_text,
):
    result = execute(
        fixture_text(f"milling/fanuc/{name}"),
        language="fanuc_mill",
        kinematics=kinematics,
        home_z=500 if name in {"indexed_table_a.nc", "indexed_table_b.nc"} else 0,
    )

    assert result.ok, result.diagnostics
    assert len(result.motions) == motion_count
    assert sum(motion.cycle_generated for motion in result.motions) == cycle_count
    assert sum(motion.arc is not None for motion in result.motions) == arc_count
    assert sum(event.kind in {"ROTARY_INDEX", "ROTARY_MOTION"} for event in result.events) == rotary_events
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx(end)

    points = [(m.start_x, m.start_y, m.start_z) for m in result.motions]
    points += [(m.end_x, m.end_y, m.end_z) for m in result.motions]
    assert all(math.isfinite(value) for point in points for value in point)
    actual_bounds = tuple(extreme(point[axis] for point in points) for axis in range(3) for extreme in (min, max))
    assert actual_bounds == pytest.approx(bounds, abs=1e-6)
    assert {diagnostic.code for diagnostic in result.diagnostics} == diagnostics
