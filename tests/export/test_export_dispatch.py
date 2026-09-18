"""GUI export dispatch between text modes and representation options."""

from __future__ import annotations

from types import SimpleNamespace

from app.gcode.exporter import (
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    PLOT_DATA_MODE,
    TURN_FULL_PROGRAM_MODE,
    export_pgm,
)
from app.gcode.kernel import execute


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
