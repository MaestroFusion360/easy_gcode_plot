from __future__ import annotations

from app.gcode.exporter import ExportOptions, export_full_program, export_result
from app.gcode.kernel import execute
from app.gcode.kernel.events import (
    HOME_RETURN,
    PROGRAM_END,
    PROGRAM_START,
    SUBPROGRAM_END,
    SUBPROGRAM_START,
    TOOL_CHANGE,
)


def test_turn_execution_events_follow_actual_program_and_subprogram_order():
    source = """\
%
O1000
T0101
G28 U0 W0
M98 P2000 L2
M30
O2000
T0202
G30 U0 W0
M99
%
"""

    result = execute(source, language="fanuc_turn")

    assert result.ok, result.diagnostics
    assert [event.kind for event in result.events] == [
        PROGRAM_START,
        TOOL_CHANGE,
        HOME_RETURN,
        SUBPROGRAM_START,
        TOOL_CHANGE,
        HOME_RETURN,
        SUBPROGRAM_END,
        SUBPROGRAM_START,
        TOOL_CHANGE,
        HOME_RETURN,
        SUBPROGRAM_END,
        PROGRAM_END,
    ]
    assert result.events[0].program_number == 1000
    assert result.events[-1].code == "M30"
    assert result.program_end == "M30"


def test_milling_tool_change_occurs_on_m6_not_tool_preselection():
    source = """\
O1
G90 G17 G21
T1
G0 X1 Y0 Z0
M6
G0 X2 Y0 Z0
M30
"""

    result = execute(source, language="fanuc_mill")

    assert result.ok, result.diagnostics
    tool_events = [event for event in result.events if event.kind == TOOL_CHANGE]
    assert len(tool_events) == 1
    assert tool_events[0].code == "M06"
    assert tool_events[0].tool == "T1"
    assert tool_events[0].previous_tool is None
    assert tool_events[0].related_block == 2
    assert result.motions[0].tool is None
    assert result.motions[1].tool == "T1"


def test_milling_g53_home_event_uses_machine_coordinates_with_wcs():
    source = """\
O1
G90 G17 G54
G0 X10 Y20 Z30
G53 G0 Z0
G53 G0 X10
M30
"""

    result = execute(
        source,
        language="fanuc_mill",
        wcs_offsets={54: (100.0, 200.0, 300.0)},
    )

    assert result.ok, result.diagnostics
    home_events = [event for event in result.events if event.kind == HOME_RETURN]
    assert [(event.code, event.axes) for event in home_events] == [("G53", ("Z",))]


def test_turn_full_export_uses_flow_events_without_dropping_same_block_controls():
    source = """\
%
O1000
G21 G18
G20 M98 P2000 L2 M8
M9 M02
O2000
G0 X10 Z0
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
    assert text.count("G20 M8") == 1
    assert text.count("M9") == 1
    assert text.count("M02") == 1


def test_expanded_execution_places_program_header_tools_and_subprogram_calls_in_event_order():
    source = """\
%
O1000
T0101
G0 X20 Z0
M98 P2000 L2
M30
O2000
T0202
G1 X30 Z-5 F100
M99
%
"""
    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    lines = export_result(
        result,
        ExportOptions(
            delimiter=True,
            sequence_numbers=True,
            sequence_start=10,
            sequence_increment=10,
        ),
    ).splitlines()

    assert lines[:2] == ["O1000", "(EXPANDED FROM LOGICAL MOTION TRACE - ANALYSIS ONLY)"]
    assert [line for line in lines if line.startswith("N")] == [
        "N10T0101",
        "N20G0 X20 Z0",
        "N30T0202",
        "N40G1 X30 Z-5 F100",
        "N50T0202",
        "N60M30",
    ]
    assert lines.count("(SUBPROGRAM O2000 START - CALL 1)") == 1
    assert lines.count("(SUBPROGRAM O2000 END - CALL 1)") == 1
    assert lines.count("(SUBPROGRAM O2000 START - CALL 2)") == 1
    assert lines.count("(SUBPROGRAM O2000 END - CALL 2)") == 1


def test_expanded_milling_tool_change_occurs_at_m6_event_not_t_preselection():
    source = """\
O1000
G21 G17 G90
T1
G0 X1 Y0 Z0
M6
G0 X2 Y0 Z0
M30
"""
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    lines = export_result(result, ExportOptions(delimiter=True, analysis_banner=False)).splitlines()

    first_motion = lines.index("G0 X1 Z0")
    tool_change = lines.index("T1 M06")
    second_motion = lines.index("G0 X2 Z0")
    assert first_motion < tool_change < second_motion


def test_expanded_turning_preserves_runtime_machine_controls_and_threading():
    source = """\
O1000
G21 G18 G54
G96 S180 M3
M8
G0 X50 Z2
G4 P500
G32 X40 Z-20 F2
G28 U0 W0
G97 S1200 M4
M9 M5
M30
"""
    result = execute(source, language="fanuc_turn", home_x=0.0, home_z=0.0)
    assert result.ok, result.diagnostics

    lines = export_result(
        result,
        ExportOptions(
            delimiter=True,
            sequence_numbers=True,
            sequence_start=10,
            sequence_increment=10,
            sequence_spacing=True,
            analysis_banner=False,
        ),
    ).splitlines()
    numbered = [line for line in lines if line.startswith("N")]
    executable = [line.split(" ", 1)[1] for line in numbered]

    assert "G18 G54" in executable
    assert "G96 S180 M3" in executable
    assert "M8" in executable
    assert "G4 P500" in executable
    assert any(line.startswith("G32 ") and line.endswith("F2") for line in executable)
    assert "G28 U0 W0" in executable
    assert "G97 S1200 M4" in executable
    assert "M9 M5" in executable
    assert [int(line.split(" ", 1)[0][1:]) for line in numbered] == list(range(10, 10 * (len(numbered) + 1), 10))


def test_expanded_milling_preserves_wcs_and_g53_as_one_executable_block():
    source = """\
O2000
G21 G17 G54
S1200 M3 M8
G0 X1 Y2 Z3
G55
G53 G0 Z0
M9 M5
M30
"""
    result = execute(
        source,
        language="fanuc_mill",
        home_z=0.0,
        wcs_offsets={54: (10.0, 20.0, 30.0), 55: (1.0, 2.0, 3.0)},
    )
    assert result.ok, result.diagnostics

    lines = export_result(result, ExportOptions(delimiter=True, analysis_banner=False)).splitlines()

    assert "G17 G54" in lines
    assert "S1200 M3 M8" in lines
    assert "G0 X1 Y2 Z3" in lines
    assert "G55" in lines
    assert lines.count("G53 G0 Z0") == 1
    assert "M9 M5" in lines
