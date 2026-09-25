"""Export options: arc encoding, incremental, sequence, and program wrappers."""

from __future__ import annotations

import pytest

from app.gcode.exporter import (
    ExportOptions,
    export_full_mill_program,
    export_full_program,
    export_result,
)
from app.gcode.kernel import execute
from app.gcode.trace_tools import arc_geometry


def test_semicolon_comment_style_is_used_by_export():
    result = execute("G0 X1 ; source comment\nM30", "fanuc_mill")

    text = export_result(result, ExportOptions(comment_style="semicolon"))

    assert ";EXPANDED FROM LOGICAL MOTION TRACE - ANALYSIS ONLY" in text
    assert "(EXPANDED FROM LOGICAL MOTION TRACE - ANALYSIS ONLY)" not in text


def test_full_program_exports_preserve_active_wcs_coordinates():
    turn_source = "G21 G18 G90 G54\nG0 X10 Z5\nM30"
    turn = execute(turn_source, "fanuc_turn", wcs_offsets={54: (100.0, 0.0, 200.0)})
    turn_text = export_full_program(turn, turn_source.splitlines(), ExportOptions(delimiter=True))
    assert "G54" in turn_text
    assert "G0 X10 Z5" in turn_text

    mill_source = "G21 G17 G90 G54\nG0 X10 Y5 Z2\nM30"
    mill = execute(mill_source, "fanuc_mill", wcs_offsets={54: (100.0, 200.0, 300.0)})
    mill_text = export_full_mill_program(mill, mill_source.splitlines(), ExportOptions(delimiter=True))
    assert "G54" in mill_text
    assert "G0 X10 Y5 Z2" in mill_text


@pytest.mark.parametrize(
    ("language", "source"),
    [
        ("fanuc_turn", "G21 G18 G90\nG0 X10 Z0\nG2 X10 Z0 I-5 K0 F10\nM30"),
        ("fanuc_mill", "G21 G17 G90\nG0 X10 Y0\nG2 X10 Y0 I-5 J0 F10\nM30"),
    ],
)
def test_r_full_circle_export_uses_two_semicircles(language, source):
    result = execute(source, language)
    text = export_result(result, ExportOptions(arc_mode=2, delimiter=True))
    arc_lines = [line for line in text.splitlines() if line.startswith("G2 ")]
    assert len(arc_lines) == 2
    assert all(" R5" in line for line in arc_lines)


def test_exporter_preserves_program_wrapper_incremental_coordinates_and_sequence_options():
    result = execute("G0 X10 Z5\nG1 X20 Z0 F100\nM30")
    text = export_result(
        result,
        ExportOptions(
            incremental=True,
            delimiter=True,
            sequence_numbers=True,
            sequence_start=10,
            sequence_increment=10,
            sequence_spacing=True,
            start_program="O1200",
            end_program="M30",
            safety_line=True,
            analysis_banner=False,
        ),
    )

    assert text.splitlines() == [
        "O1200",
        "N10 G0 G18 G40 G80",
        "N20 G0 U10 W5",
        "N30 G1 U10 W-5 F100",
        "",
        "N40 M30",
    ]


def test_delimited_sequence_numbers_always_separate_number_from_gcode():
    result = execute("G0 X10\nG1 X20 F100\nM30")
    text = export_result(
        result,
        ExportOptions(
            delimiter=True,
            sequence_numbers=True,
            sequence_start=810,
            sequence_increment=10,
            sequence_spacing=False,
            analysis_banner=False,
        ),
    )

    assert "N810 G0 X10" in text
    assert "N810G0" not in text


def test_incremental_export_forces_incremental_ijk_even_when_absolute_arc_mode_is_selected():
    source = "G21 G17 G90\nG0 X10 Y0\nG3 X20 Y10 I0 J10 F100\nM30"
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_result(
        result,
        ExportOptions(
            arc_mode=1,
            incremental=True,
            delimiter=True,
            analysis_banner=False,
        ),
    )
    arc_line = next(line for line in text.splitlines() if line.startswith("G3 "))

    assert "X10 Y10" in arc_line
    assert "I0 J10" in arc_line
    assert "I10 J10" not in arc_line


def test_exporter_arc_modes_are_explicit_and_linearization_removes_g2_g3():
    result = execute("G18 G0 X0 Z0\nG2 X20 Z0 I5 K0 F50\nM30")

    absolute = export_result(result, ExportOptions(arc_mode=1, delimiter=True, analysis_banner=False))
    radius = export_result(result, ExportOptions(arc_mode=2, delimiter=True, analysis_banner=False))
    linear = export_result(result, ExportOptions(arc_mode=3, delimiter=True, analysis_banner=False))
    coarse = export_result(
        result,
        ExportOptions(arc_mode=3, delimiter=True, analysis_banner=False, linearization_tolerance=0.1),
    )
    fine = export_result(
        result,
        ExportOptions(arc_mode=3, delimiter=True, analysis_banner=False, linearization_tolerance=0.001),
    )

    assert "I5" in absolute and "K0" in absolute
    assert " R5" in radius
    assert " I" not in radius and " K" not in radius
    assert "G2 " not in linear and "G3 " not in linear
    assert linear.count("G1 ") > 100
    assert fine.count("G1 ") > coarse.count("G1 ")


def test_turning_relative_ijk_export_round_trips_nonzero_x_arc_geometry():
    source = "G21 G18\nG0 X20 Z0\nG2 X20 Z0 I-10 K0 F100\nM30"
    original = execute(source, language="fanuc_turn")
    assert original.ok, original.diagnostics

    text = export_result(
        original,
        ExportOptions(arc_mode=0, delimiter=True, analysis_banner=False),
    )
    assert "I-10" in text

    round_trip = execute(text, language="fanuc_turn")
    assert round_trip.ok, round_trip.diagnostics
    expected_arc = arc_geometry(original.motions[-1])
    actual_arc = arc_geometry(round_trip.motions[-1])
    assert expected_arc is not None
    assert actual_arc is not None
    assert actual_arc[4] == pytest.approx(expected_arc[4], abs=0.001)
    assert actual_arc[6:] == pytest.approx(expected_arc[6:], abs=0.001)
