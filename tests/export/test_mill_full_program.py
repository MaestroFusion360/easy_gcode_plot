"""Mill full-program expansion and round-trip behaviour."""

from __future__ import annotations

import pytest
from gcode_samples import MILLING_ARC_PLANES, MILLING_CYCLES, MILLING_HELIX_FULL_CIRCLE

from app.cli import main
from app.gcode.exporter import ExportOptions, export_full_mill_program
from app.gcode.kernel import execute
from app.gcode.trace_tools import arc_geometry


def _assert_mill_round_trip(source: str, exported: str) -> None:
    original = execute(source, language="fanuc_mill")
    round_trip = execute(exported, language="fanuc_mill")
    assert original.ok, original.diagnostics
    assert round_trip.ok, round_trip.diagnostics
    assert len(round_trip.motions) == len(original.motions)

    for expected, actual in zip(original.motions, round_trip.motions, strict=True):
        assert actual.move == expected.move
        assert actual.plane == expected.plane
        assert (actual.end_x, actual.end_y, actual.end_z) == pytest.approx(
            (expected.end_x, expected.end_y, expected.end_z),
            abs=0.001,
        )
        if expected.move == 0 or expected.feed is None:
            if expected.move != 0:
                assert actual.feed is None
        else:
            assert actual.feed == pytest.approx(expected.feed, abs=0.001)

        if expected.move in (2, 3):
            expected_arc = arc_geometry(expected)
            actual_arc = arc_geometry(actual)
            assert expected_arc is not None
            assert actual_arc is not None
            assert actual_arc[4] == pytest.approx(expected_arc[4], abs=0.001)
            assert actual_arc[6:] == pytest.approx(expected_arc[6:], abs=0.001)


def test_mill_full_program_expands_cycles_and_round_trips_trace():
    result = execute(MILLING_CYCLES, language="fanuc_mill")
    assert result.ok, result.diagnostics
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)

    text = export_full_mill_program(
        result,
        MILLING_CYCLES.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    code_lines = [line for line in text.splitlines() if not line.startswith("(")]
    assert not any(line.startswith(("G81", "G82", "G83", "G84", "G85", "G86")) for line in code_lines)
    assert text.count("EXPANDED MILL CYCLE") == 5
    _assert_mill_round_trip(MILLING_CYCLES, text)


@pytest.mark.parametrize("source", [MILLING_ARC_PLANES, MILLING_HELIX_FULL_CIRCLE])
def test_mill_full_program_round_trips_arc_planes_and_full_circle(source):
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    _assert_mill_round_trip(source, text)


def test_mill_full_program_flattens_polar_coordinates_without_leaving_g16_active(fixture_text):
    source = fixture_text("milling/polar_drilling.nc")
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert "G16" not in text
    assert "G15" not in text
    assert "X86.60254 Y50" in text
    assert "X-86.60254 Y50" in text
    assert "Y-100" in text
    _assert_mill_round_trip(source, text)


def test_mill_full_program_flattens_subprograms_and_preserves_inch_incremental_controls(fixture_text):
    source = fixture_text("milling/subprogram.nc")
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert "G20" in text
    assert "G91" in text
    assert "T1 M06" in text
    assert "G43 H1" in text
    assert "M98" not in text
    assert "M99" not in text
    _assert_mill_round_trip(source, text)


def test_mill_full_program_preserves_source_controls_comments_and_program_end(fixture_text):
    source = fixture_text("milling/wcs_test.nc")
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert "(CONTOUR)" in text
    assert "(FREZA D10)" in text
    assert "T1 M6" in text
    assert "S2000 M3" in text
    assert "G43 H1 M8" in text
    for wcs in ("G54", "G55", "G56", "G57"):
        assert wcs in text
    assert "M9" in text
    assert "M5" in text
    assert "M1" in text
    assert text.count("M30") == 1
    _assert_mill_round_trip(source, text)


def test_mill_full_program_preserves_m02_tool_and_dwell_control():
    source = """\
%
O42
G21 G17 G90
T4 M6
S1200 M3
G0 X1 Y2 Z3
G4 P250
M9 M02
%
"""
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert text.count("M02") == 1
    assert "M30" not in text
    assert "T4 M6" in text
    assert "G4 P250" in text
    assert "M9" in text
    _assert_mill_round_trip(source, text)


def test_mill_full_program_applies_delimiter_to_compact_home_return_block():
    source = "G0G90G54\nG0G91G28Z0\nG90X400\nM30"
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, analysis_banner=False),
    )

    assert "G0 G91 G28 Z0" in text
    assert "G0G91G28Z0" not in text


def test_mill_full_program_exports_compensation_transition_without_double_compensation():
    source = """\
G21 G17 G90 G40
T1 M6
G0 X-72 Y-72
G1 Z-10 F3000
G41 G1 X-40 F1200
G1 X-40 Y30
G1 X40 Y30
G40 G1 Y-72
M30
"""
    tools = {"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}}
    result = execute(source, language="fanuc_mill", milling_tools=tools)
    assert result.ok, result.diagnostics
    assert any(motion.source_kind == "cutter_compensation_transition" for motion in result.motions)
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)

    text = export_full_mill_program(
        result,
        source.splitlines(),
        ExportOptions(delimiter=True, leading_zero=True, analysis_banner=False),
    )

    assert "G41" not in text
    assert "G42" not in text
    round_trip = execute(text, language="fanuc_mill", milling_tools=tools)
    assert round_trip.ok, round_trip.diagnostics
    assert len(round_trip.motions) == len(result.motions)
    for expected, actual in zip(result.motions, round_trip.motions, strict=True):
        assert actual.move == expected.move
        assert (actual.end_x, actual.end_y, actual.end_z) == pytest.approx(
            (expected.end_x, expected.end_y, expected.end_z), abs=0.001
        )


def test_compensation_transition_ownership_survives_repeated_subprogram_occurrences():
    source = """\
O1
G21 G17 G90 G40
T1 M6
M98 P2 L2
M30
O2
G0 X-72 Y-72
G1 Z-10 F3000
G41 G1 X-40 F1200
G1 X-40 Y30
G1 X40 Y30
G40 G1 Y-72
M99
"""
    tools = {"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}}
    result = execute(source, language="fanuc_mill", milling_tools=tools)
    assert result.ok, result.diagnostics
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    transition_steps = [step for step in result.execution_steps if step.source_block == 9]
    assert [step.emitted_count for step in transition_steps] == [2, 2]

    text = export_full_mill_program(result, source.splitlines())

    assert "M98" not in text
    assert "M99" not in text
    assert "G41" not in text
    assert sum(motion.source_kind == "cutter_compensation_transition" for motion in result.motions) == 2


def test_cli_allows_program_mode_for_milling(tmp_path, fixture_text):
    source = tmp_path / "mill.nc"
    output = tmp_path / "expanded.nc"
    source_text = fixture_text("milling/subprogram.nc")
    source.write_text(source_text, encoding="utf-8")

    assert (
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--mode",
                "program",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    _assert_mill_round_trip(source_text, output.read_text(encoding="utf-8"))
