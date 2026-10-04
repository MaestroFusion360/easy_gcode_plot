"""Native exact stop and modal work-offset deactivation."""

import pytest

from app.gcode.kernel import execute


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


def test_g60_g64_preserve_geometry_and_feed():
    result = native("G0 X10\nG60\nG1 X20 F100\nG60 G1 X30\nG64\nX40\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert [m.end_x for m in result.motions] == [10, 20, 30, 40]
    assert [m.feed for m in result.motions] == [None, 100, 100, 100]
    assert [e.code for e in result.events if e.kind == "SINUMERIK_NATIVE_OPERATION"] == ["G60", "G60", "G64"]


def test_path_control_does_not_cancel_or_reject_native_drilling_cycle():
    result = native("G0 Z20\nF100\nMCALL CYCLE81(10,0,2,-5)\nG60\nX10\nG64\nX20\nMCALL\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert len([m for m in result.motions if m.source_kind == "cycle" and m.move == 1]) == 2


@pytest.mark.parametrize("distance,move", [("G90", "X20"), ("G91", "X-90")])
def test_g500_rebases_without_motion_and_g55_restores_offset(distance, move):
    result = native(f"G55 G0 X10\nG500\n{distance} G1 {move} F100\nG90 G55\nG1 X30\nM30", wcs_offsets={55: (100, 0, 0)})
    assert result.ok and result.complete and not result.diagnostics
    assert [(m.start_x, m.end_x) for m in result.motions] == [(0, 110), (110, 20), (20, 130)]
    assert result.execution_steps[1].active_wcs == 500
    assert result.execution_steps[1].emitted_count == 0
    assert result.execution_steps[1].position == (110, 0, 0)


def test_g500_accepts_configured_translation():
    result = native("G55 G0 X10\nG500 G1 X20 F100\nM30", wcs_offsets={55: (100, 0, 0), 500: (5, 6, 7)})
    assert result.ok and result.complete, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == (25, 0, 0)


@pytest.mark.parametrize("code", ["G60", "G500"])
def test_codes_are_not_enabled_in_iso(code):
    assert not native(f"G291\n{code}\nM30").ok


def test_g500_does_not_enable_unknown_fanuc_position_command():
    result = execute("G500 G1 X20 F100", language="fanuc_mill")
    assert not result.ok and not result.motions
