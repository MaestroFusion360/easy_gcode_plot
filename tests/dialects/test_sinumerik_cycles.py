"""Native drilling semantics and the user's paired cycle programs."""

from math import dist
from pathlib import Path

import pytest

from app.gcode.export.options import ExportOptions
from app.gcode.export.trace import export_result
from app.gcode.kernel import execute

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/milling"


def _native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


def _end(motion):
    return motion.end_x, motion.end_y, motion.end_z


def test_paired_cycle_programs_cut_same_holes_and_depths():
    native = _native((FIXTURES / "cycles_sin840d.mpf").read_text())
    fanuc = execute((FIXTURES / "cycles_fanuc.nc").read_text(), language="fanuc_mill")
    assert native.ok and native.complete and not native.diagnostics
    assert fanuc.ok and fanuc.complete and not fanuc.diagnostics
    native_feeds = [m for m in native.motions if m.move == 1]
    fanuc_feeds = [m for m in fanuc.motions if m.move == 1]
    # CYCLE81/82 and explicitly expanded chip breaking agree, including feed.
    for mpf, nc in zip(native_feeds[:62], fanuc_feeds[:62], strict=True):
        assert mpf.feed == nc.feed == 400
        assert dist(_end(mpf), _end(nc)) < 0.0002
        assert dist((mpf.start_x, mpf.start_y, mpf.start_z), (nc.start_x, nc.start_y, nc.start_z)) < 0.0002
    # Deep drilling has real parameter differences: decreasing step vs Q1.
    assert len(native_feeds) > len(fanuc_feeds)
    for motions in (native_feeds, fanuc_feeds):
        assert {(m.end_x, m.end_y) for m in motions} == {(-25, 10), (25, 10)}
        for x in (-25, 25):
            assert min(m.end_z for m in motions if m.end_x == x) == pytest.approx(-17.262, abs=0.0002)


@pytest.mark.parametrize("events", [False, True])
def test_native_cycle_trace_export_roundtrip(events):
    native = _native((FIXTURES / "cycles_sin840d.mpf").read_text())
    trace = export_result(native, ExportOptions(include_execution_events=events, safety_line=True, delimiter=True))
    replay = execute(trace, language="fanuc_mill")
    assert replay.ok and replay.complete and not replay.diagnostics
    assert len(replay.motions) == len(native.motions)
    for source, target in zip(native.motions, replay.motions, strict=True):
        assert source.move == target.move
        assert dist(_end(source), _end(target)) < 0.000002
    assert "MCALL" not in trace and "CYCLE83" not in trace


def test_mcall_declaration_repeated_position_and_cancel_with_wcs():
    result = _native(
        "G90 G54 G0 X2 Y3 Z15\nF100\nMCALL CYCLE81(5,-1,5,,9)\nX2 Y3\nX2 Y3\nMCALL\nG0 X4\nM30",
        wcs_offsets={54: (10, 20, 100)},
    )
    assert result.ok and result.complete and not result.diagnostics
    cuts = [m for m in result.motions if m.move == 1]
    assert len(cuts) == 2
    assert [_end(m) for m in cuts] == [(12, 23, 90)] * 2
    assert all(m.start_z == 104 for m in cuts)
    assert _end(result.motions[-1]) == (14, 23, 105)


def test_cycle83_decreasing_pecks_and_return_plane():
    result = _native("G0 Z15\nF400\nMCALL CYCLE83(5,-1,5,-7,,-2,,0.1,0,0,1,1,,0.5,0,0,0,0,0,1001110)\nX2\nMCALL\nM30")
    assert result.ok and result.complete and not result.diagnostics
    cuts = [m for m in result.motions if m.move == 1]
    assert [m.end_z for m in cuts] == pytest.approx([-2, -2.9, -3.7, -4.4, -5, -5.5, -6, -6.5, -7])
    assert cuts[0].start_z == 4
    assert cuts[1].start_z == pytest.approx(-1.4)
    assert _end(result.motions[-1]) == (2, 0, 5)


@pytest.mark.parametrize("operation", ["G291", "G18", "G0 Z5", "M30"])
def test_active_native_cycle_rejects_unmodeled_state_changes(operation):
    result = _native("MCALL CYCLE81(5,-1,5,-10,)\n" + operation + "\nX99")
    assert not result.ok and not result.complete
    assert result.diagnostics[0].line == 2
    assert not result.motions


@pytest.mark.parametrize("declaration", ["MCALL CYCLE84(5,-1,5,-10,)", "MCALL CYCLE81(5,-1,5,0,)", "CYCLE800(1)"])
def test_unmodeled_cycle_declarations_fail_closed(declaration):
    result = _native(declaration + "\nX99")
    assert not result.ok and not result.complete
    assert not result.motions


def test_cam_tapping_matches_fanuc_g84_and_trace_replay():
    native = _native((FIXTURES / "tapping_sin840d.mpf").read_text())
    fanuc = execute((FIXTURES / "tapping_fanuc.nc").read_text(), language="fanuc_mill")
    replay = execute(export_result(native, ExportOptions()), language="fanuc_mill")
    for result in (native, fanuc, replay):
        assert result.ok and result.complete and not result.diagnostics
        assert len(result.motions) == len(native.motions)
        for actual, expected in zip(result.motions, native.motions, strict=True):
            assert actual.move == expected.move
            assert _end(actual) == pytest.approx(_end(expected))
            assert actual.feed == expected.feed
    feeds = [m for m in native.motions if m.move == 1]
    assert len(feeds) == 8
    assert [m.end_z for m in feeds] == [1, 15] * 4
    assert all(m.feed == 500 for m in feeds)


def test_tapping_pitch_is_not_rpm_or_modal_feed_and_cancellation_restores_feed():
    result = _native(
        "S500 M3\nF17\nG0 Z10\nMCALL CYCLE84(5,0,2,,9,0.2,3,,1.25,0,500,0,3,0,0,0)\nX2\nX2\nMCALL\nG1 X3\nM30"
    )
    assert result.ok and result.complete and not result.diagnostics
    feeds = [m for m in result.motions if m.move == 1]
    assert [m.feed for m in feeds] == [625] * 4 + [17]
    assert [m.end_z for m in feeds[:4]] == [-9, 2] * 2
    signals = [signal for step in result.execution_steps for signal in step.signals]
    assert sum(signal.kind == "spindle_reverse" for signal in signals) == 2
    assert sum(signal.kind == "dwell" and signal.value == 0.2 for signal in signals) == 2


@pytest.mark.parametrize(
    "index,value",
    [
        (6, "5"),
        (7, "8"),
        (8, "0"),
        (8, "-1"),
        (10, "0"),
        (11, "700"),
        (12, "1"),
        (13, "2"),
        (15, "2"),
        (16, "2"),
        (21, "1"),
        (22, "2"),
        (23, "1"),
        (5, "-1"),
    ],
)
def test_unmodeled_tapping_options_fail_before_hole(index, value):
    args = "5,0,2,-9,,0,3,,1,0,500,500,0,1,,0,,,,,,0,0,1001002".split(",")
    args[index] = value
    result = _native("S500 M3\nMCALL CYCLE84(" + ",".join(args) + ")\nX99")
    assert not result.ok and not result.complete
    assert not result.motions
    assert result.diagnostics[0].line == 2


def test_tapping_spindle_change_cannot_emit_hole_with_stale_feed():
    result = _native("S500 M3\nMCALL CYCLE84(5,0,2,-9,,0,3,,1,0,500,500)\nS700\nX99")
    assert not result.ok and not result.complete and not result.motions
