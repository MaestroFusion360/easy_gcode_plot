from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from gcode_samples import MILLING_ARC_PLANES, MILLING_CYCLES, MILLING_HELIX_FULL_CIRCLE

from app.cli import main
from app.gcode.exporter import (
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    PLOT_DATA_MODE,
    TURN_FULL_PROGRAM_MODE,
    ExportOptions,
    export_cycle_groups,
    export_full_mill_program,
    export_full_program,
    export_pgm,
    export_result,
)
from app.gcode.kernel import execute
from app.gcode.trace_tools import arc_geometry

FIXTURES = Path(__file__).parent / "fixtures"


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


def test_cli_trace_serializes_one_logical_arc(tmp_path):
    source = tmp_path / "arc.nc"
    output = tmp_path / "trace.json"
    source.write_text("G0 X0 Z0\nG2 X10 Z0 R5 F100\nM30\n", encoding="utf-8")

    assert main(["trace", str(source), "--output", str(output)]) == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["complete"] is True
    assert len(data["motions"]) == 1
    assert data["motions"][0]["move"] == 2
    assert data["motions"][0]["radius"] == 5.0


def test_cli_reads_cp1251_through_shared_nc_text_contract(tmp_path, capsys):
    source = tmp_path / "cp1251.nc"
    source.write_bytes("(ПРОГРАММА)\nG21 G18\nG0 X20 Z0\nM30\n".encode("cp1251"))

    assert main(["parse", str(source), "--encoding", "cp1251"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True


def test_cli_parse_returns_structured_error_code(tmp_path, capsys):
    source = tmp_path / "bad.nc"
    source.write_text("G1 X#999 Z0\n", encoding="utf-8")

    assert main(["parse", str(source)]) == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["complete"] is False
    assert data["diagnostics"][0]["code"] == "UNDEFINED_MACRO"


def test_cli_analyze_and_export_consume_same_execution_result(tmp_path):
    source = tmp_path / "line.nc"
    analysis = tmp_path / "analysis.json"
    exported = tmp_path / "expanded.nc"
    source.write_text("G0 X3 Z4\nG1 X6 Z8 F10\nM30\n", encoding="utf-8")

    assert main(["analyze", str(source), "-o", str(analysis)]) == 0
    assert main(["export", str(source), "-o", str(exported)]) == 0
    analysis_data = json.loads(analysis.read_text(encoding="utf-8"))
    assert analysis_data["complete"] is True
    assert analysis_data["motion_count"] == 2
    assert "G01 X6 Z8 F10" in exported.read_text(encoding="utf-8")


def test_cli_cycle_export_includes_complete_final_id_g71_contour(tmp_path):
    exported = tmp_path / "cycle71-id-expanded.nc"

    assert (
        main(
            [
                "export",
                str(FIXTURES / "turning" / "cycle71_ID.nc"),
                "--mode",
                "cycles",
                "-o",
                str(exported),
            ]
        )
        == 0
    )

    lines = exported.read_text(encoding="utf-8").splitlines()
    contour_start = lines.index("G00 X89.6 Z1")
    contour = lines[contour_start:-2]
    assert contour[0] == "G00 X89.6 Z1"
    assert contour[1] == "G01 X89.568007 Z0.075386 F0.25"
    assert "G01 X84.219901 Z-30.027723 F0.25" in contour
    assert "G01 X76.447921 Z-29.933473 F0.25" in contour
    assert contour[-1] == "G01 X75.3 Z-145 F0.25"
    assert len(contour) > 100
    assert "G00 X89.8 Z1" not in lines
    assert lines[-2:] == ["G00 X72 Z-145", "G00 X72 Z1"]


def _window_export_harness(source: str, *, language: str, export_mode: int, arc_mode: int = 0):
    result = execute(source, language=language)
    assert result.ok, result.diagnostics
    return SimpleNamespace(
        execution_result=result,
        exportMode=export_mode,
        exportArcMode=arc_mode,
        latheMode=language == "fanuc_turn",
        incrMode=False,
        forceAdr=False,
        seqNum=False,
        seqNumStart=1,
        seqNumIncr=1,
        seqNumSpacing=False,
        delim=True,
        leadingZero=False,
        startPgmExp="",
        endPgmExp="",
        safLine=False,
        ui=SimpleNamespace(editor=SimpleNamespace(text=lambda: source)),
    )


def test_gui_export_dispatch_keeps_text_modes_and_arc_options():
    turn_source = "G21 G18\nG0 X20 Z0\nG3 X40 Z-10 I0 K-10 F100\nM30"

    converted = _window_export_harness(
        turn_source,
        language="fanuc_turn",
        export_mode=EXPANDED_EXECUTION_MODE,
        arc_mode=2,
    )
    converted_text = export_pgm(converted)
    assert " R10" in converted_text

    converted.exportMode = PLOT_DATA_MODE
    plot_text = export_pgm(converted)
    assert "G2 " not in plot_text and "G3 " not in plot_text

    converted.incrMode = True
    plot_text = export_pgm(converted)
    assert "G91" not in plot_text

    converted.exportMode = TURN_FULL_PROGRAM_MODE
    turn_full = export_pgm(converted)
    assert "EXPANDED TURN PROGRAM" in turn_full

    mill_source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30"
    mill = _window_export_harness(
        mill_source,
        language="fanuc_mill",
        export_mode=MILL_FULL_PROGRAM_MODE,
    )
    mill_full = export_pgm(mill)
    assert "EXPANDED MILL PROGRAM" in mill_full


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
        "N10 G00 G17 G40 G49 G80 G90",
        "N20 G0 U10 W5",
        "N30 G1 U10 W-5 F100",
        "",
        "N40 M30",
    ]


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


def test_cli_rejects_cycle_mode_for_milling(tmp_path):
    source = tmp_path / "mill.nc"
    output = tmp_path / "expanded.nc"
    source.write_text("G21 G17 G0 X0 Y0 Z0\nM30\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "export",
                str(source),
                "--lang",
                "fanuc_mill",
                "--mode",
                "cycles",
                "-o",
                str(output),
            ]
        )
    assert exc.value.code == 2


def test_cli_export_rejects_invalid_partial_execution(tmp_path, capsys):
    source = tmp_path / "invalid_arc.nc"
    output = tmp_path / "invalid_arc_export.nc"
    source.write_text("G21 G17 G90\nG1 X10 Y0 F100\nG2 X20 Y0 R1\nM30\n", encoding="utf-8")

    assert main(["export", str(source), "--lang", "fanuc_mill", "-o", str(output)]) == 2
    assert not output.exists()
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert any(item["code"] == "INVALID_GEOMETRY" for item in data["diagnostics"])
