"""FULL preserves source structure and unfolds label-dependent execution."""

import re
from dataclasses import replace

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.full import normalize_full_program
from app.gcode.kernel import execute
from app.gcode.trace_tools import motion_length


@pytest.mark.parametrize(
    "source",
    [
        "#1=0\nWHILE [#1 LT 3] DO1\n#1=#1+1\nG1 X[#1*10] F100\nEND1\nM30\n",
        "#1=10\nIF [#1 EQ 10] GOTO 30\nN20 G1 X99 F100\nN30 G1 X#1 F100\nM30\n",
        "O1\nG91\nM98 P2 L3\nM30\nO2\nG1 X10 F100\nM99\n",
        "O1\nG65 P2 A10\nM30\nO2\nG1 X#1 F100\nM99\n",
        "O1\nG91\nG0M98P2L3\nM30\nO2\nG1X10F100\nM99\n",
    ],
)
def test_full_expands_macro_and_calls_before_renumbering(source):
    original = execute(source, language="fanuc_mill")
    assert original.ok and original.complete, original.diagnostics
    options = ExportOptions(sequence_numbers=True, sequence_start=100, sequence_increment=10, delimiter=True)
    output = normalize_full_program(original, source, options)
    assert not any(token in output for token in ("#", "GOTO", "WHILE", "END1", "M98", "M99", "G65"))
    replay = execute(output, language="fanuc_mill")
    assert replay.ok and replay.complete, replay.diagnostics
    assert [(m.end_x, m.end_y, m.end_z) for m in replay.motions] == [
        (m.end_x, m.end_y, m.end_z) for m in original.motions
    ]
    assert sum(map(motion_length, replay.motions)) == pytest.approx(sum(map(motion_length, original.motions)))


def test_full_preserves_drilling_transforms_comments_and_blank_lines():
    source = "%\nO5\n(setup)\n\nG90 G21 G17\nG0 X10 Y0 Z5\nG99 G81 X10 Y0 Z-2 R1 F100\nG80\nM30\n%\n"
    result = execute(source, language="fanuc_mill")
    assert result.ok
    output = normalize_full_program(result, source, ExportOptions(delimiter=True))
    assert output == source


def test_full_rejects_incomplete_execution_before_formatting():
    source = "G1 X10 F100\nM30\n"
    result = execute(source, language="fanuc_mill")
    with pytest.raises(ValueError, match="complete"):
        normalize_full_program(replace(result, complete=False), source)


def test_full_source_without_jumps_is_idempotent():
    source = "O10\nN2 G00 X1.5000 Y0 Z5\nN7 G01 X2.000 F100\nM30\n"
    options = ExportOptions(delimiter=True, sequence_numbers=True, sequence_increment=10)
    output = normalize_full_program(execute(source, language="fanuc_mill"), source, options)
    assert normalize_full_program(execute(output, language="fanuc_mill"), output, options) == output


@pytest.mark.parametrize("fixture", ["thread.nc", "lathe_cnc_macro_test.nc"])
@pytest.mark.parametrize("system", ["A", "B"])
def test_full_turning_cycles_and_macros_preserve_executed_path(fixture_text, fixture, system):
    source = fixture_text("turning/" + fixture)
    if system == "B":
        source = re.sub(
            r"G(32|50|98|99)\b", lambda m: "G" + {"32": "33", "50": "92", "98": "94", "99": "95"}[m[1]], source
        )
    result = execute(source, language="fanuc_turn", lathe_gcode_system=system)
    assert result.ok and result.complete, result.diagnostics
    output = normalize_full_program(result, source, ExportOptions(delimiter=True, sequence_numbers=True))
    code = "\n".join(line.split("(")[0] for line in output.splitlines())
    assert not re.search(r"\bG7[0-6]\b|#|GOTO|M98|M99", code)
    replay = execute(output, language="fanuc_turn", lathe_gcode_system=system)
    assert replay.ok and replay.complete, replay.diagnostics
    assert len(replay.motions) == len(result.motions)
    for actual, expected in zip(replay.motions, result.motions, strict=True):
        assert (actual.end_x, actual.end_z) == pytest.approx((expected.end_x, expected.end_z), abs=0.001)
        assert actual.threading == expected.threading


def test_full_cycle_setup_does_not_create_false_position_gaps(fixture_text):
    source = fixture_text("turning/basic_turning_cycles.NC")
    result = execute(source, language="fanuc_turn")
    output = normalize_full_program(result, source)
    replay = execute(output, language="fanuc_turn")
    assert replay.ok and replay.complete
    assert len(replay.motions) == len(result.motions)
    for actual, expected in zip(replay.motions, result.motions, strict=True):
        assert (actual.start_x, actual.start_z, actual.end_x, actual.end_z) == pytest.approx(
            (expected.start_x, expected.start_z, expected.end_x, expected.end_z),
            abs=1e-5,
        )


def test_full_rejects_stale_source_snapshot():
    result = execute("G1 X10 F100\nM30", language="fanuc_mill")
    with pytest.raises(ValueError, match="does not match"):
        normalize_full_program(result, "G1 X20 F100\nM30")


def test_full_type_b_macros_keep_source_feed_and_threading_codes():
    source = "#1=20\nG18 G21 G95\nG92 S2500\nG97 S500 M3\nG0 X#1 Z2\nG33 Z-10 F1.5\nG91\nG1 X[#1/10] F0.2\nM30"
    result = execute(source, language="fanuc_turn", lathe_gcode_system="B")
    assert result.ok and result.complete, result.diagnostics
    output = normalize_full_program(result, source, ExportOptions(delimiter=True))
    replay = execute(output, language="fanuc_turn", lathe_gcode_system="B")
    assert replay.ok and replay.complete, replay.diagnostics
    assert "G98" not in output and "G99" not in output and "G32" not in output
    assert [(m.end_x, m.end_z, m.threading, m.feed) for m in replay.motions] == [
        (m.end_x, m.end_z, m.threading, m.feed) for m in result.motions
    ]
