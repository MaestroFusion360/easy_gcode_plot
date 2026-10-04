"""Replay exported Siemens drilling cycles with FANUC execution semantics."""

from pathlib import Path

import pytest

from app.cli import main
from app.gcode.export.options import ExportOptions
from app.gcode.export.sinumerik import convert_full_program_to_fanuc
from app.gcode.export.validation import validate_full_program_dialect_conversion
from app.gcode.program_execution import execute_program
from app.gcode.trace_tools import motion_length
from app.ui.windows.main_window_file_ops import _convert_full_program_dialect

FIXTURES = Path(__file__).parents[1] / "fixtures" / "milling"


def execute(source, dialect, **options):
    return execute_program(source, language="fanuc_mill", source_dialect=dialect, **options)[0]


def replay(source, **options):
    result = execute(source, "sinumerik", **options)
    assert result.ok and result.complete, result.diagnostics
    output = convert_full_program_to_fanuc(
        source, source_result=result, export_options=ExportOptions(delimiter=True), execution_options=options
    )
    target = execute(output, "fanuc", **options)
    assert target.ok and target.complete and not target.diagnostics
    assert sum(map(motion_length, target.motions)) == pytest.approx(sum(map(motion_length, result.motions)), abs=1e-8)
    assert [m.end_z for m in target.motions if m.move == 1] == pytest.approx(
        [m.end_z for m in result.motions if m.move == 1]
    )
    assert [m.feed for m in target.motions if m.move == 1] == pytest.approx(
        [m.feed for m in result.motions if m.move == 1]
    )
    return output, target, result


def test_user_cycles_fixture_exports_via_cli(tmp_path):
    output = tmp_path / "cycles_fanuc.nc"
    assert (
        main(
            [
                "export",
                str(FIXTURES / "cycles_sin840d.mpf"),
                "-o",
                str(output),
                "--mode",
                "full",
                "--target-dialect",
                "fanuc_mill",
            ]
        )
        == 0
    )
    text = output.read_text()
    assert "G81" in text and "G80" in text
    assert not any(word in text for word in ("MCALL", "CYCLE81", "CYCLE82", "CYCLE83", "CYCLE800", "SUPA"))
    source = (FIXTURES / "cycles_sin840d.mpf").read_text()
    validate_full_program_dialect_conversion(execute(source, "sinumerik"), text, "fanuc_mill", source_dialect="fanuc")


def test_gui_cycle_export_uses_the_same_converter_and_matches_reference_drilling():
    source = (FIXTURES / "cycles_sin840d.mpf").read_text()
    output, target, original = replay(source)
    assert _convert_full_program_dialect(source, original, 1, "sinumerik", ExportOptions(delimiter=True), {}) == output
    reference = execute((FIXTURES / "cycles_fanuc.nc").read_text(), "fanuc")
    assert reference.ok and reference.complete
    # Both posts have the same first four drilling holes. Their deep-drilling
    # algorithms differ: Siemens uses degression, FANUC uses constant G83 Q1.
    actual = [m for m in target.motions if m.cycle_generated and m.move == 1][:4]
    expected = [m for m in reference.motions if m.cycle_generated and m.move == 1][:4]
    assert len(actual) == len(expected) == 4
    for a, b in zip(actual, expected, strict=True):
        assert (a.end_x, a.end_y, a.end_z, a.feed) == pytest.approx((b.end_x, b.end_y, b.end_z, b.feed), abs=0.0002)


@pytest.mark.parametrize("code,dwell", [(81, 0), (81, 0.25), (82, 0), (82, 2)])
@pytest.mark.parametrize("initial_z", [15, 5, 4, 3])
def test_drilling_planes_dwell_modal_holes_and_cancellation(code, dwell, initial_z):
    source = (
        f"G710 G17 G90 G94\nG0 Z{initial_z}\nF123\n"
        f"MCALL CYCLE{code}(5,0,4,-10,,{dwell},0,0,0)\nX2 Y3\nX7\nMCALL\nG0 Z20\nM30\n"
    )
    output, target, _ = replay(source)
    assert ("G82" if dwell else "G81") in output
    assert [s.value for s in target.signals if s.kind == "dwell"] == ([dwell, dwell] if dwell else [])
    assert target.motions[-1].end_z == 20


@pytest.mark.parametrize("units", ["G710", "G700"])
@pytest.mark.parametrize("mode", ["G90", "G91"])
def test_native_peck_degression_feed_factor_and_incremental_holes(units, mode):
    source = (
        f"{units} G17 G90 G94\nG0 Z5\nF200\n"
        "MCALL CYCLE83(5,0,2,-6,,,1,0.25,0,0,0.5,1,,0.5,0,0,0,0,0,1001110)\n"
        f"{mode}\nX1 Y1\nX2\nMCALL\nG0 Z10\nM30\n"
    )
    output, target, original = replay(source)
    assert "G83" not in output
    assert len([m for m in target.motions if m.move == 1]) == len([m for m in original.motions if m.move == 1])


@pytest.mark.parametrize("dwell", [0, 1.25])
def test_rigid_tapping_returns_at_feed_to_safety_then_rapid_to_rtp(dwell):
    source = (
        "G710 G17 G90 G94\nS500 M3\nG0 Z15\n"
        f"MCALL CYCLE84(5,0,2,-9,,{dwell},3,,1.25,0,500,500)\nX2 Y3\nX7\nMCALL\nM5 M30\n"
    )
    output, target, _ = replay(source)
    assert "M29" in output and "G99 G84" in output
    assert [(m.start_z, m.end_z) for m in target.motions if m.move == 1] == [(2, -9), (-9, 2)] * 2
    assert sum(s.kind == "rigid_tapping" for s in target.signals) == 2


def test_existing_tapping_fixture_replays():
    replay((FIXTURES / "tapping_sin840d.mpf").read_text())


def test_cycle_parameters_are_reevaluated_at_each_hole():
    source = "G710 G17 G90\nG0 Z10\nF100\nR1=-5\nMCALL CYCLE81(5,0,2,R1,,0,0,0,0)\nX1\nR1=-8\nX2\nMCALL\nM30\n"
    _, target, _ = replay(source)
    assert [m.end_z for m in target.motions if m.move == 1] == [-5, -8]


def test_invalid_native_cycle_mode_still_blocks_conversion():
    source = "G710 G90\nG0 Z10\nF100\nMCALL CYCLE81(5,0,2,-5,,0,0,0,0)\nX1\nG0 Z15\nX2\nMCALL\nM30\n"
    with pytest.raises(ValueError, match="source execution"):
        convert_full_program_to_fanuc(source)


def test_cycle_holes_preserve_work_offset_and_inline_controls():
    source = "G710 G90\nG54\nG0 Z10\nF100\nMCALL CYCLE81(5,0,2,-5,,0,0,0,0)\nX1 Y3 M8\nX2 F200\nMCALL\nM9 M30\n"
    _, target, _ = replay(source, wcs_offsets={54: (20, 30, 40)})
    assert [m.end_z for m in target.motions if m.move == 1] == [35, 35]


@pytest.mark.parametrize("replacement", ["R3", "Z-11", "F124"])
def test_cycle_conversion_validation_still_rejects_changed_path_or_feed(replacement):
    source = "G710\nG0 Z15\nF123\nMCALL CYCLE81(5,0,4,-10,,0,0,0,0)\nX2\nMCALL\nM30\n"
    output, _, original = replay(source)
    address = {"R3": "R4", "Z-11": "Z-10", "F124": "F123"}[replacement]
    with pytest.raises(ValueError, match="geometry"):
        validate_full_program_dialect_conversion(
            original, output.replace(address, replacement), "fanuc_mill", source_dialect="fanuc"
        )


@pytest.mark.parametrize("metadata", ["G60", "G64"])
def test_native_hole_path_control_is_removed_before_fanuc_emission(metadata):
    source = f"G710\nG0 Z10\nF100\nMCALL CYCLE81(5,0,2,-5,,0,0,0,0)\nX1 {metadata}\nMCALL\nM30"
    output, _, _ = replay(source)
    assert metadata not in output


@pytest.mark.parametrize("word", ["G71", "G641", "G710"])
def test_native_cycle_mode_change_is_rejected_before_target_emission(word):
    source = f"G710\nG0 Z10\nF100\nMCALL CYCLE81(5,0,2,-5,,0,0,0,0)\nX1 {word}\nMCALL\nM30"
    with pytest.raises(ValueError, match="source execution"):
        convert_full_program_to_fanuc(source)


def test_modal_cycle_return_parameter_change_reestablishes_g98_initial_plane():
    source = "G710\nG0 Z10\nF100\nR1=5\nMCALL CYCLE81(R1,0,2,-5,,0,0,0,0)\nX1\nR1=3\nX2\nMCALL\nM30"
    _, target, _ = replay(source)
    assert [m.end_z for m in target.motions if m.move == 0 and m.start_z == -5] == [5, 3]
