"""Current export architecture contract after the 1.9.2 refactor."""

from __future__ import annotations

import re

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.export.full import normalize_full_program
from app.gcode.kernel import execute
from app.gcode.trace_tools import motion_length


def _assert_path_matches(reference, replay, *, tolerance=0.002):
    assert replay.ok and replay.complete, replay.diagnostics
    expected = sum(map(motion_length, reference.motions))
    actual = sum(map(motion_length, replay.motions))
    assert actual == pytest.approx(expected, abs=max(tolerance, expected * 2e-5))
    assert (replay.motions[-1].end_x, replay.motions[-1].end_y, replay.motions[-1].end_z) == pytest.approx(
        (reference.motions[-1].end_x, reference.motions[-1].end_y, reference.motions[-1].end_z), abs=0.001
    )


def _dwell_seconds(result):
    return sum(
        signal.value or 0.0 for step in result.execution_steps for signal in step.signals if signal.kind == "dwell"
    )


@pytest.mark.parametrize(
    ("target", "language", "system", "source", "dialect"),
    [
        (
            "fanuc_mill",
            "fanuc_mill",
            None,
            "G21 G17 G90\nT2 M6\nS3000 M3\nG0 X10 Y0 Z5\nG1 Z0 F200\nG3 X0 Y10 I-10 J0\nM5 M9\nM30",
            "fanuc",
        ),
        (
            "sinumerik_iso",
            "fanuc_mill",
            None,
            "G21 G17 G90\nT2 M6\nS3000 M3\nG0 X10 Y0 Z5\nG1 Z0 F200\nG3 X0 Y10 I-10 J0\nM5 M9\nM30",
            "sinumerik",
        ),
        (
            "sinumerik_840d",
            "fanuc_mill",
            None,
            "G21 G17 G90\nT2 M6\nS3000 M3\nG0 X10 Y0 Z5\nG1 Z0 F200\nG3 X0 Y10 I-10 J0\nM5 M9\nM30",
            "sinumerik",
        ),
        (
            "fanuc_lathe_a",
            "fanuc_turn",
            "A",
            "G21 G18 G90\nT0202\nG97 S500 M3\nG0 X20 Z5\nG1 Z0 F100\nG3 X40 Z-10 I0 K-10\nM5 M9\nM30",
            "fanuc",
        ),
        (
            "fanuc_lathe_b",
            "fanuc_turn",
            "B",
            "G21 G18 G90\nT0202\nG97 S500 M3\nG0 X20 Z5\nG1 Z0 F100\nG3 X40 Z-10 I0 K-10\nM5 M9\nM30",
            "fanuc",
        ),
    ],
)
def test_all_five_posts_round_trip_resolved_geometry(target, language, system, source, dialect):
    original = execute(source, language=language)
    assert original.ok and original.complete, original.diagnostics
    output = convert_resolved_program(original, target, ExportOptions(delimiter=True))
    replay_options = {"lathe_gcode_system": system} if system else {}
    replay = execute(output, language=language, source_dialect=dialect, **replay_options)
    _assert_path_matches(original, replay)


def test_full_is_source_linked_while_expanded_is_resolved_geometry():
    source = "O1\n#1=5\nG90 G0 X#1\nM98 P2 L2\nM30\nO2\nG91 G1 X#1 F100\nM99"
    result = execute(source, language="fanuc_mill")
    assert result.ok and result.complete, result.diagnostics

    full = normalize_full_program(result, source, ExportOptions(delimiter=True))
    expanded = convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True))

    assert not re.search(r"#|\bM98\b|\bM99\b", full)
    assert not re.search(r"#|\bM98\b|\bM99\b", expanded)
    assert "O1" in full
    assert "O1" not in expanded
    _assert_path_matches(result, execute(full, language="fanuc_mill"))
    _assert_path_matches(result, execute(expanded, language="fanuc_mill"))


def test_sinumerik_native_profile_owns_comments_program_header_and_arc_syntax():
    source = "(TOOL T2)\nG21 G17 G90\nT2 M6\nG0 X10 Y0\nG3 X0 Y10 I-10 J0 F100\nM30"
    result = execute(source, language="fanuc_mill")
    absolute = convert_resolved_program(
        result,
        "sinumerik_840d",
        ExportOptions(delimiter=True, arc_mode=1, start_program="O0003"),
    )
    radius = convert_resolved_program(result, "sinumerik_840d", ExportOptions(delimiter=True, arc_mode=2))

    assert "; TOOL T2" in absolute
    # The mandatory mode frame stays first, but user start text is still honored.
    assert absolute.splitlines()[0] == "G290"
    assert "O0003" in absolute
    assert absolute.splitlines()[1] == "O0003"
    assert "I=AC(0)" in absolute and "J=AC(0)" in absolute
    assert "CR=10" in radius
    assert not re.search(r"(?:^|\s)R10(?:\s|$)", radius, flags=re.MULTILINE)


@pytest.mark.parametrize("kinematics", ["4ax_table_b", "5ax_table_bc_angled"])
def test_selected_kinematics_without_rotary_words_does_not_block_expanded_conversion(kinematics):
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30"
    result = execute(source, language="fanuc_mill", kinematics=kinematics)
    assert result.ok and result.complete, result.diagnostics
    assert result.rotary_axes
    assert not any(event.kind in {"ROTARY_INDEX", "ROTARY_MOTION"} for event in result.events)

    output = convert_resolved_program(result, "sinumerik_840d", ExportOptions(delimiter=True))
    replay = execute(output, language="fanuc_mill", source_dialect="sinumerik")
    _assert_path_matches(result, replay)


def test_actual_rotary_address_still_blocks_expanded_conversion():
    source = "G90 G0 X0 Y0 Z0\nB30\nG1 X10 Y0 Z0 F100\nM30"
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_b")
    assert result.ok and result.complete, result.diagnostics
    assert any(event.kind == "ROTARY_INDEX" for event in result.events)
    with pytest.raises(ValueError, match="three-axis XYZ"):
        convert_resolved_program(result, "sinumerik_840d")


@pytest.mark.parametrize(
    ("language", "target", "source"),
    [
        (
            "fanuc_mill",
            "fanuc_mill",
            "O1000\nG65 P2000 A10. M8 T7 X20. F500.\nM30\nO2000\nG1 X#1 F100\nM99",
        ),
        (
            "fanuc_turn",
            "fanuc_lathe_a",
            "O1000\nG65 P2000 A10. M8 T7 X20. F500.\nM30\nO2000\nG1 X#1 F100\nM99",
        ),
        (
            "fanuc_turn",
            "fanuc_lathe_b",
            "G21 G18 G90\nG0 X100 Z0\nG1 X106 C1.4 F100\nG1 X110 A20 R1.4\nM30",
        ),
    ],
)
def test_nonrotary_abc_words_do_not_trigger_expanded_rotary_guard(language, target, source):
    execute_options = {}
    if language == "fanuc_turn":
        execute_options["lathe_gcode_system"] = "A"
    result = execute(source, language=language, **execute_options)
    assert result.ok and result.complete, result.diagnostics
    assert not any(event.kind in {"ROTARY_INDEX", "ROTARY_MOTION"} for event in result.events)

    output = convert_resolved_program(result, target, ExportOptions(delimiter=True))
    assert output.strip()


def test_current_expanded_preserves_cycle_effects_that_192_lost():
    cycle82 = "G21 G17 G90\nT1 M6\nS500 M3\nG0 Z5\nG99 G82 X2 Y3 Z-5 R2 P100 F100\nX4\nG80\nM30"
    result82 = execute(cycle82, language="fanuc_mill")
    output82 = convert_resolved_program(result82, "fanuc_mill", ExportOptions(delimiter=True))
    replay82 = execute(output82, language="fanuc_mill")
    assert _dwell_seconds(result82) == pytest.approx(0.2)
    assert _dwell_seconds(replay82) == pytest.approx(_dwell_seconds(result82))
    assert output82.count("G4 P100") == 2
    _assert_path_matches(result82, replay82)

    cycle84 = "G21 G17 G90\nT1 M6\nS500 M3\nG0 Z5\nG99 G84 X2 Y3 Z-5 R2 P100 F100\nX4\nG80\nM30"
    result84 = execute(cycle84, language="fanuc_mill")
    output84 = convert_resolved_program(result84, "fanuc_mill", ExportOptions(delimiter=True))
    replay84 = execute(output84, language="fanuc_mill")
    assert _dwell_seconds(replay84) == pytest.approx(_dwell_seconds(result84))
    assert output84.count("M4") == 2
    assert output84.count("M3") >= 3
    _assert_path_matches(result84, replay84)


def test_post_files_define_the_current_controller_contract():
    assert load_post_profile("fanuc_mill")["format"]["radiusAddress"] == "R"
    assert load_post_profile("fanuc_lathe_a")["motion"]["threadMove"] == "G32"
    assert load_post_profile("fanuc_lathe_b")["motion"]["threadMove"] == "G33"
    assert load_post_profile("sinumerik_iso")["program"]["mode"] == "G291"
    native = load_post_profile("sinumerik_840d")
    assert native["program"]["mode"] == "G290"
    assert native["format"]["absoluteCenterSyntax"] == "AC"
    assert native["format"]["radiusAddress"] == "CR="
    assert "safety" in native["program"]
