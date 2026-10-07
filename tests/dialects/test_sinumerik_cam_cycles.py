"""Audit the user's extended/classic CAM cycle fixtures without rewriting them."""

from pathlib import Path

import pytest
from export_signatures import motion_traces_match

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.kernel import execute

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/milling/sinumerik"
PROFILES = [("ext_cycles.mpf", True), ("no_ext_cycles.mpf", False)]


def _source(fixture):
    return (FIXTURES / fixture).read_text(encoding="utf-8-sig")


def _native(source, extended):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=extended)


def _section(fixture, title):
    block = _source(fixture).split(f'MSG ("{title}")', 1)[1].split("MSG (", 1)[0]
    # Each operation gets the same initial state; its own setup remains intact.
    return "G17 G710 G90 G94\nS1000 M3\nF400\nG0 Z15\n" + block


@pytest.mark.parametrize(
    "fixture,extended,line,message",
    [
        ("ext_cycles.mpf", True, 216, "deep tapping are not modeled"),
        ("no_ext_cycles.mpf", False, 200, "classic (01/2008) interface"),
    ],
)
def test_complete_cam_cycle_fixture_reports_first_unsupported_operation(fixture, extended, line, message):
    source = _source(fixture)
    result = _native(source, extended)
    assert not result.ok and not result.complete
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "UNSUPPORTED_SINUMERIK_CYCLE"
    assert diagnostic.line == line
    assert diagnostic.raw == source.splitlines()[line - 1]
    assert message in diagnostic.message
    assert result.motions
    holes = [event.drilling for event in result.events if event.drilling is not None]
    assert len(holes) == (8 if extended else 6)


@pytest.mark.parametrize(
    "title",
    [
        "Rapid out",
        "Dwell and rapid out",
        "Chip breaking",
        "Deep drilling",
        "Break-through drilling",
        "Guided deep drilling",
        "Circular mill",
        "Thread mill",
    ],
)
def test_common_cam_operations_have_matching_classic_and_extended_geometry(title):
    extended = _native(_section("ext_cycles.mpf", title), True)
    classic = _native(_section("no_ext_cycles.mpf", title), False)
    for result in (extended, classic):
        assert result.ok and result.complete and not result.diagnostics
        assert any(motion.move != 0 for motion in result.motions)
    assert motion_traces_match(extended, classic, tolerance=0.000002)


@pytest.mark.parametrize("title", ["Tap", "Right tap"])
def test_extended_cam_tapping_has_correct_depth_pitch_and_reversal(title):
    result = _native(_section("ext_cycles.mpf", title), True)
    assert result.ok and result.complete and not result.diagnostics
    cuts = [motion for motion in result.motions if motion.move == 1]
    assert [motion.end_z for motion in cuts] == [-16, 4]
    assert [motion.feed for motion in cuts] == [800, 800]
    assert sum(signal.kind == "spindle_reverse" for signal in result.signals) == 1


@pytest.mark.parametrize("fixture,extended", PROFILES)
@pytest.mark.parametrize(
    "title,code",
    [
        ("Tap with chip breaking", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("Left tap", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("Reaming", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("Boring", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("Stop boring", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("Fine boring", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("Back boring", "UNSUPPORTED_SINUMERIK_M_CODE"),
    ],
)
def test_unsupported_cam_operations_stop_before_cutting(fixture, extended, title, code):
    result = _native(_section(fixture, title), extended)
    assert not result.ok and not result.complete
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == code
    assert all(motion.move == 0 for motion in result.motions)
    assert not any(event.drilling is not None for event in result.events)


@pytest.mark.parametrize("fixture,extended", PROFILES)
@pytest.mark.parametrize("target", ["fanuc_mill", "sinumerik_840d"])
def test_supported_cam_prefix_export_preserves_geometry(fixture, extended, target):
    stop = "Tap with chip breaking" if extended else "Tap"
    source = _source(fixture).split(f'MSG ("{stop}")', 1)[0] + "M30\n"
    before = _native(source, extended)
    assert before.ok and before.complete and not before.diagnostics
    text = convert_resolved_program(before, target, ExportOptions(delimiter=True, decimal_places=6))
    after = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target == "sinumerik_840d" else "fanuc",
        sinumerik_840d_sl=extended,
    )
    assert after.ok and after.complete and not after.diagnostics
    assert motion_traces_match(before, after, tolerance=0.000002, allow_split_cycle_rapids=True)
