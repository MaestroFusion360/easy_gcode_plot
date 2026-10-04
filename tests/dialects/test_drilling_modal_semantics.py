"""FANUC canned-cycle reference planes, feeds and incremental hole depths."""

import pytest

from app.gcode.kernel import execute


def mill(source, dialect="fanuc"):
    return execute(source, language="fanuc_mill", source_dialect=dialect)


@pytest.mark.parametrize("cycle", [73, 81, 82, 83, 84, 85, 86])
@pytest.mark.parametrize("units,scale", [("G21", 1), ("G20", 25.4)])
def test_incremental_depth_is_relative_to_r_plane(cycle, units, scale):
    result = mill(f"{units} G90 G0 Z50\nG91 G99 G{cycle} X10 Z-25 R-45 Q5 F100\nX10\nG80\nM30")
    assert result.ok, result.diagnostics
    cuts = [m for m in result.motions if m.move == 1]
    assert min(m.end_z for m in cuts) == pytest.approx(-20 * scale)
    assert all(m.end_z < m.start_z for m in cuts if m.end_z < 5 * scale)
    assert result.motions[-1].end_x == pytest.approx(20 * scale)
    assert result.motions[-1].end_z == pytest.approx(5 * scale)


def test_incremental_modal_r_uses_original_initial_plane():
    result = mill("G90 G0 Z50\nG91 G99 G81 X10 Z-25 R-45 F100\nX10 Z-30 R-45\nG80\nM30")
    assert result.ok, result.diagnostics
    assert [m.end_z for m in result.motions if m.move == 1] == [-20, -25]
    assert result.motions[-1].end_z == 5


@pytest.mark.parametrize("cycle", [73, 81, 82, 83, 84, 85, 86])
@pytest.mark.parametrize("dialect,mode", [("fanuc", ""), ("sinumerik", "G291\n")])
def test_g98_after_g99_returns_to_saved_initial_plane(cycle, dialect, mode):
    result = mill(mode + f"G90 G0 Z50\nG99 G{cycle} X10 Z-10 R5 Q5 F100\nG98 X20\nG80\nM30", dialect)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_z == 50


def test_g80_resets_initial_plane_for_next_cycle():
    result = mill("G90 G0 Z50\nG99 G81 X10 Z-10 R5 F100\nG80\nG0 Z30\nG98 G81 X20 Z-10 R5\nG80\nM30")
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_z == 30


def test_initial_plane_below_r_does_not_return_below_r():
    result = mill("G90 G0 Z1\nG98 G81 X10 Z-10 R5 F100\nG80\nM30")
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_z == 5


@pytest.mark.parametrize("feed", ["", " F0", " F-10"])
def test_missing_or_nonpositive_drilling_feed_does_not_emit_zero_feed_motion(feed):
    result = mill("G99 G81 X5 Z-5 R2" + feed)
    assert not result.ok and result.diagnostics
    assert not result.motions
    assert any(d.code == "INVALID_DRILLING_FEED" for d in result.diagnostics)


@pytest.mark.parametrize("operands", ["X5 Z-5 F100", "X5 R2 F100"])
def test_first_hole_requires_modal_depth_and_r_plane(operands):
    result = mill("G99 G81 " + operands)
    assert not result.ok and not result.motions
    assert any(d.code == "INCOMPLETE_DRILLING_CYCLE" for d in result.diagnostics)


def test_positive_modal_feed_is_valid_without_repeating_f_on_cycle():
    result = mill("F100\nG99 G81 X5 Z-5 R2\nX10\nG80\nM30")
    assert result.ok, result.diagnostics
    assert [m.feed for m in result.motions if m.move == 1] == [100, 100]
