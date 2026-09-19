"""Turn full-program and cycle-group export behaviour."""

from __future__ import annotations

import pytest

from app.gcode.exporter import ExportOptions, export_cycle_groups, export_full_program
from app.gcode.kernel import execute


@pytest.mark.parametrize(
    "cycle_source",
    [
        """\
G21 G18
G0 X80 Z5
G72 W2 R0.5
G72 P10 Q20 U0.2 W0.1 F0.2
N10 G0 Z0
N20 G1 X40
M30
""",
        """\
G21 G18
G0 X80 Z5
G73 U10 W5 R3
G73 P10 Q20 U0.2 W0.1 F0.2
N10 G0 X70 Z0
N20 G1 X40 Z-20
M30
""",
    ],
)
def test_turn_cycle_export_uses_execution_step_as_one_logical_group(cycle_source):
    result = execute(cycle_source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    text = export_cycle_groups(
        result,
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert text.count("EXPANDED TURN CYCLE") == 1
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)

    full = export_full_program(
        result,
        cycle_source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )
    round_trip = execute(full, language="fanuc_turn")
    assert round_trip.ok, round_trip.diagnostics
    expected_positions = [(motion.end_x, motion.end_z) for motion in result.motions]
    actual_positions = [(motion.end_x, motion.end_z) for motion in round_trip.motions]
    assert len(actual_positions) == len(expected_positions)
    for actual, expected in zip(actual_positions, expected_positions, strict=True):
        assert actual == pytest.approx(expected, abs=0.001)


def test_turn_full_program_preserves_m02_short_tool_and_source_units():
    source = """\
%
O42
T4
G20 G18
G97 S1000 M3
G0 X2 Z1
G1 X1 Z0 F0.01
M9 M02
%
"""
    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    text = export_full_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert text.count("M02") == 1
    assert "M30" not in text
    assert "\nT4\n" in text
    assert "T0004" not in text
    assert "G20" in text
    assert "G00 X2 Z1" in text
    assert "M9" in text

    round_trip = execute(text, language="fanuc_turn")
    assert round_trip.ok, round_trip.diagnostics
    assert [(motion.end_x, motion.end_z) for motion in round_trip.motions] == pytest.approx(
        [(motion.end_x, motion.end_z) for motion in result.motions]
    )


def test_turn_full_program_flattens_repeated_subprogram_execution_in_runtime_order():
    source = """\
%
O1000
G21 G18
M98 P2000 L2
M02
O2000
G0 X10 Z0
G1 X5 Z-1 F0.1
M99
%
"""
    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    text = export_full_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert "M98" not in text
    assert "M99" not in text
    assert text.count("G00 X10 Z0") == 2
    assert text.count("G01 X5 Z-1 F0.1") == 2
    assert text.count("M02") == 1
