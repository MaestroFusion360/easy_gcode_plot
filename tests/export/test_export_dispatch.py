"""GUI export dispatch between text modes and representation options."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.gcode.exporter import (
    EXPANDED_EXECUTION_MODE,
    MILL_FULL_PROGRAM_MODE,
    TURN_FULL_PROGRAM_MODE,
    export_pgm,
)
from app.gcode.kernel import execute


def _window_export_harness(
    source: str,
    *,
    language: str,
    export_mode: int,
    arc_mode: int = 0,
    skip_optional_blocks: bool = False,
    kinematics: str | None = None,
    source_dialect: str = "fanuc",
):
    result = execute(
        source,
        language=language,
        skip_optional_blocks=skip_optional_blocks,
        kinematics=kinematics,
        source_dialect=source_dialect,
    )
    assert result.ok, result.diagnostics
    return SimpleNamespace(
        execution_result=result,
        exportMode=export_mode,
        exportArcMode=arc_mode,
        latheMode=language == "fanuc_turn",
        incrMode=False,
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

    converted.exportMode = TURN_FULL_PROGRAM_MODE
    turn_full = export_pgm(converted)
    assert "G3 X40 Z-10 I0 K-10 F100" in turn_full

    mill_source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30"
    mill = _window_export_harness(
        mill_source,
        language="fanuc_mill",
        export_mode=MILL_FULL_PROGRAM_MODE,
    )
    mill_full = export_pgm(mill)
    assert "G1 X10 Y0 Z0 F100" in mill_full


def test_expanded_execution_exports_the_trace_after_block_skip():
    source = "/G1 X10 F100\nG1 X20 F100\nM30"

    for language in ("fanuc_turn", "fanuc_mill"):
        window = _window_export_harness(
            source,
            language=language,
            export_mode=EXPANDED_EXECUTION_MODE,
            skip_optional_blocks=True,
        )
        exported = export_pgm(window)

        assert "X10" not in exported
        assert "X20" in exported


@pytest.mark.parametrize(("target", "mode"), [(2, "G291"), (3, "G290"), (5, "G290")])
@pytest.mark.parametrize("numbered", [False, True])
def test_gui_expanded_fanuc_to_sinumerik_keeps_selected_post_mode_first(target, mode, numbered):
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30"
    window = _window_export_harness(source, language="fanuc_mill", export_mode=EXPANDED_EXECUTION_MODE)
    window.exportTargetCnc = target
    window.seqNum = numbered
    window.startPgmExp = "O9999"

    lines = export_pgm(window).splitlines()

    assert lines[0] == mode
    assert sum(mode in line for line in lines) == 1
    assert "O9999" in lines[1:]


@pytest.mark.parametrize("mode", ["G290", "G291"])
def test_gui_expanded_auto_uses_sinumerik_source_controller(mode):
    source = f"{mode}\nG90 G0 X0 Y0 Z5\nG1 X10 F100\nM30"
    window = _window_export_harness(
        source, language="fanuc_mill", export_mode=EXPANDED_EXECUTION_MODE, source_dialect="sinumerik"
    )
    window.exportTargetCnc = 0

    assert export_pgm(window).splitlines()[0] == mode


@pytest.mark.parametrize(
    ("profile", "rotary_word"),
    [("5ax_table_ac_angled", "A30 C45"), ("5ax_table_bc_angled", "B30 C45")],
)
def test_g43_4_gui_full_program_preserves_source_and_expanded_export_is_rejected(profile, rotary_word):
    source = f"G90 G0 X0 Y0 Z0\nG43.4 H1\nG1 X10 Y20 Z30 {rotary_word} F100\nG49\nM30"
    window = _window_export_harness(
        source,
        language="fanuc_mill",
        export_mode=MILL_FULL_PROGRAM_MODE,
        kinematics=profile,
    )

    assert export_pgm(window) == source

    window.exportMode = EXPANDED_EXECUTION_MODE
    with pytest.raises(ValueError, match="cannot preserve G43.4 TCP rotary commands"):
        export_pgm(window)
