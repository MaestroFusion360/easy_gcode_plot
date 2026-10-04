"""Kernel regression snapshots for the checked-in turning program corpus."""

from __future__ import annotations

import math

import pytest

from app.gcode.kernel import execute


@pytest.mark.parametrize(
    ("name", "motion_count", "cycle_count", "end", "bounds", "diagnostics"),
    [
        ("basic_turning_cycles.NC", 4028, 3916, (74, 100), (0, 305.4, -224.7, 100), {"UNSUPPORTED_G_CODE"}),
        ("compensation_control_off.nc", 190, 153, (128.27, 25.4), (-1.6, 138.43, -112.697, 25.4), set()),
        ("compensation_control_on.nc", 188, 151, (128.27, 25.4), (-1.6, 138.43, -112.697, 25.4), set()),
        ("cycle71_ID.nc", 38, 37, (72, 1), (0, 89.6, -145, 1), set()),
        ("drill.nc", 118, 55, (0, 16), (0, 0, -19.09, 16), {"UNSUPPORTED_M_CODE"}),
        ("face_groove.nc", 50, 46, (110, 20), (0, 110, -20, 20), set()),
        ("od_rough_finish.nc", 46, 43, (100, 20), (0, 100, -45, 20), set()),
        ("oem_header.nc", 4, 0, (100, 20), (0, 100, -30, 20), {"UNSUPPORTED_G_CODE"}),
        ("radius_profile.nc", 6, 0, (100, 20), (0, 100, -38, 20), set()),
        ("taper_thread.nc", 32, 25, (80, 20), (0, 80, -45, 20), set()),
        ("thread.nc", 102, 50, (80, 0), (47.992, 80, -52, 0), set()),
    ],
)
def test_turning_fixture_trace_contract(name, motion_count, cycle_count, end, bounds, diagnostics, fixture_text):
    result = execute(fixture_text(f"turning/{name}"), language="fanuc_turn")

    assert result.ok, result.diagnostics
    assert len(result.motions) == motion_count
    assert sum(motion.cycle_generated for motion in result.motions) == cycle_count
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx(end)
    points = [(m.start_x, m.start_z) for m in result.motions] + [(m.end_x, m.end_z) for m in result.motions]
    assert all(math.isfinite(value) for point in points for value in point)
    assert (
        min(point[0] for point in points),
        max(point[0] for point in points),
        min(point[1] for point in points),
        max(point[1] for point in points),
    ) == pytest.approx(bounds)
    assert {diagnostic.code for diagnostic in result.diagnostics} == diagnostics


def test_g70_profile_motion_code_survives_later_g40_word():
    source = """\
G21 G18
G0 X20 Z0
G71 U2 R0.2
G71 P10 Q20 U0 W0 F0.2
N10 G1 X20 Z0
G3 X40 Z-10 R10
N20 G1 G40 X42
G70 P10 Q20
M30
"""
    result = execute(source, language="fanuc_turn")

    assert result.ok, result.diagnostics
    finish = [motion for motion in result.motions if motion.source_raw == "G70 P10 Q20"]
    assert [motion.move for motion in finish if motion.move in (2, 3)] == [3]
    assert any(motion.move == 1 and motion.end_x == pytest.approx(42) for motion in finish)


def test_r_profile_cycle_is_independent_of_ijk_source_mode():
    source = """\
G21 G18
G0 X100 Z5
G71 U2 R0.5
G71 P10 Q20 U0 W0 F0.2
N10 G0 X60
G1 Z0
G3 X80 Z-10 R10
N20 G1 G40 X90
G70 P10 Q20
M30
"""
    results = [execute(source, language="fanuc_turn", source_arc_type=mode) for mode in (1, 2, 3)]

    assert all(result.ok for result in results)
    assert [len(result.motions) for result in results] == [len(results[0].motions)] * 3
    assert [
        [(motion.arc.center, motion.arc.radius) for motion in result.motions if motion.arc] for result in results
    ] == [[(motion.arc.center, motion.arc.radius) for motion in results[0].motions if motion.arc]] * 3


@pytest.mark.parametrize(
    ("source_arc_type", "diagnostic_code"),
    [(2, "INVALID_TURNING_ARC_CENTER"), (3, "TURNING_ARC_REQUIRES_R")],
)
def test_invalid_ijk_profile_discards_entire_g71_and_g70_cycles(source_arc_type, diagnostic_code):
    source = """\
G21 G18
G0 X100 Z5
G71 U2 R0.5
G71 P10 Q20 U0 W0 F0.2
N10 G0 X60
G1 Z0
G3 X80 Z-10 I0 K-10
N20 G1 X90
G70 P10 Q20
M30
"""
    result = execute(source, language="fanuc_turn", source_arc_type=source_arc_type)

    assert not result.ok
    assert not any(motion.cycle_generated for motion in result.motions)
    assert result.execution_steps[3].emitted_count == 0
    assert result.execution_steps[8].emitted_count == 0
    assert {diagnostic_code} == {d.code for d in result.diagnostics if d.severity == "error"}
