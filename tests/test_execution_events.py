from __future__ import annotations

from app.gcode.exporter import ExportOptions, export_full_program
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
