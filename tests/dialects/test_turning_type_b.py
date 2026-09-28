"""Type B uses the existing turning executor through source-code normalization."""

from __future__ import annotations

import pytest

from app.cli import main
from app.gcode.kernel import execute
from app.gcode.kernel.turning.dialect import canonical_operation, supported_codes
from app.gcode.kernel.turning.type_a import TurningOperation
from app.gcode.kernel.turning.type_b import TYPE_B_SUPPORTED_G_CODES, type_b_operation


@pytest.mark.parametrize(
    ("type_a", "type_b"),
    [(32, 33), (90, 77), (92, 78), (94, 79), (98, 94), (99, 95), (50, 92)],
)
def test_equivalent_codes_have_one_operation(type_a, type_b):
    assert canonical_operation(type_a, "A") == canonical_operation(type_b, "B")


def test_type_b_vocabulary_exposes_distance_modes():
    assert type_b_operation(90) == TurningOperation.DISTANCE_ABSOLUTE
    assert type_b_operation(91) == TurningOperation.DISTANCE_INCREMENTAL
    assert type_b_operation(77) == TurningOperation.TURN_CYCLE
    assert 32 not in TYPE_B_SUPPORTED_G_CODES


def test_g91_is_type_b_distance_mode_only():
    assert 91 not in supported_codes("A")
    assert 91 in supported_codes("B")
    a = execute("G91\nG1 X10 Z-1 F100\nM30", lathe_gcode_system="A")
    b = execute("G91\nG1 X10 Z-1 F100\nM30", lathe_gcode_system="B")
    assert any(item.code == "UNSUPPORTED_G_CODE" for item in a.diagnostics)
    assert b.ok, b.diagnostics
    assert (b.motions[-1].end_x, b.motions[-1].end_z) == (10, -1)


@pytest.mark.parametrize("system", ["A", "B"])
@pytest.mark.parametrize("code", [190, 191])
def test_nonstandard_x_mode_gcodes_are_unsupported(system, code):
    assert code not in supported_codes(system)
    result = execute(f"G{code}\nG1 X10 Z-1 F100\nM30", lathe_gcode_system=system)
    assert any(item.code == "UNSUPPORTED_G_CODE" for item in result.diagnostics)


@pytest.mark.parametrize(
    ("type_a", "type_b"),
    [
        ("G32 X20 Z-10 F1", "G33 X20 Z-10 F1"),
        ("G90 X20 Z-10 F1", "G77 X20 Z-10 F1"),
        ("G92 X20 Z-10 F1", "G78 X20 Z-10 F1"),
        ("G94 X20 Z-10 F1", "G79 X20 Z-10 F1"),
    ],
)
def test_equivalent_motion_programs(type_a, type_b):
    prefix = "G21 G18\nG0 X30 Z0\n"
    a = execute(prefix + type_a + "\nM30", lathe_gcode_system="A")
    b = execute(prefix + type_b + "\nM30", lathe_gcode_system="B")
    assert a.ok, a.diagnostics
    assert b.ok, b.diagnostics
    assert [(m.move, m.start_x, m.start_z, m.end_x, m.end_z) for m in a.motions] == [
        (m.move, m.start_x, m.start_z, m.end_x, m.end_z) for m in b.motions
    ]


def test_type_b_distance_mode_switches_for_each_axis():
    source = "G21 G18\nG90 G0 X20 Z0\nG91 G1 X5 F100\nZ-3\nX2 Z-2\nG90 G1 X40 Z-10\nM30"
    result = execute(source, lathe_gcode_system="B")
    assert result.ok, result.diagnostics
    assert [(m.end_x, m.end_z) for m in result.motions] == [(20, 0), (25, 0), (25, -3), (27, -5), (40, -10)]


@pytest.mark.parametrize(("system", "code"), [("A", 77), ("B", 32), ("B", 50), ("B", 98), ("B", 99)])
def test_other_system_codes_are_unsupported(system, code):
    assert code not in supported_codes(system)
    result = execute(f"G{code} X20 Z-1\nM30", lathe_gcode_system=system)
    assert any(d.code == "UNSUPPORTED_G_CODE" for d in result.diagnostics)
    assert not result.motions


def test_type_b_feed_modes_do_not_collide_with_cycles():
    result = execute("G21 G18\nG0 X30 Z0\nG94 G77 X20 Z-5 F100\nG95 G79 X10 Z-2 F0.2\nM30", lathe_gcode_system="B")
    assert result.ok, result.diagnostics
    assert any(m.cycle_generated for m in result.motions)


def test_type_b_arc_uses_incremental_endpoints():
    source = "G21 G18\nG90 G0 X20 Z0\nG91 G2 X10 Z-5 R10 F100\nM30"
    result = execute(source, lathe_gcode_system="B", source_arc_type=3)
    assert result.ok, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == (30, -5)


def test_type_b_canned_cycle_after_distance_mode_change():
    source = "G21 G18\nG90 G0 X30 Z0\nG91\nG77 X-10 Z-5 F100\nM30"
    result = execute(source, lathe_gcode_system="B")
    assert result.ok, result.diagnostics
    assert any(m.cycle_generated for m in result.motions)


def test_type_b_g71_profile_obeys_g91():
    source = "G21 G18\nG90 G0 X60 Z1\nG71 U2 R0.2\nG71 P10 Q20 U0.2 W0 F0.25\nN10 G91 G0 X-10\nN20 G1 Z-10\nM30"
    result = execute(source, lathe_gcode_system="B")
    assert result.ok, result.diagnostics
    assert any(m.cycle_generated for m in result.motions)


def test_type_b_g71_profile_inherits_g91_before_profile():
    source = "G21 G18\nG90 G0 X60 Z1\nG91\nG71 U2 R0.2\nG71 P10 Q20 U0.2 W0 F0.25\nN10 G0 X-10\nN20 G1 Z-10\nM30"
    result = execute(source, lathe_gcode_system="B")
    assert result.ok, result.diagnostics
    assert any(m.cycle_generated for m in result.motions)


def test_cli_trace_batch_and_export_accept_type_b(tmp_path):
    source = tmp_path / "type_b.nc"
    source.write_text("G21 G18\nG90 G0 X20 Z0\nG91 G1 X5 Z-2 F100\nM30\n", encoding="utf-8")
    trace = tmp_path / "trace.json"
    assert main(["trace", str(source), "--lathe-gcode-system", "B", "-o", str(trace)]) == 0
    assert '"end_x": 25.0' in trace.read_text(encoding="utf-8")
    assert (
        main(
            ["batch", str(tmp_path), "--extensions", ".nc", "--lathe-gcode-system", "B", "-o", str(tmp_path / "report")]
        )
        == 0
    )
    assert main(["export", str(source), "--lathe-gcode-system", "B", "-o", str(tmp_path / "exported.nc")]) == 0
